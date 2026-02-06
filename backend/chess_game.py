from typing import Optional, List, Tuple, Dict, Set
from enum import Enum
from dataclasses import dataclass
from copy import deepcopy


class PieceType(Enum):
    PAWN = "pawn"
    ROOK = "rook"
    KNIGHT = "knight"
    BISHOP = "bishop"
    QUEEN = "queen"
    KING = "king"


class Color(Enum):
    WHITE = "white"
    BLACK = "black"

    def opposite(self) -> "Color":
        return Color.BLACK if self == Color.WHITE else Color.WHITE


@dataclass
class Position:
    """Represents a position on the chess board."""
    row: int  # 0-7, where 0 is rank 1 (white's back rank)
    col: int  # 0-7, where 0 is 'a' file

    def __hash__(self) -> int:
        return hash((self.row, self.col))

    def is_valid(self) -> bool:
        """Check if position is within board bounds."""
        return 0 <= self.row < 8 and 0 <= self.col < 8

    def offset(self, row_delta: int, col_delta: int) -> "Position":
        """Create a new position with an offset."""
        return Position(self.row + row_delta, self.col + col_delta)

    def to_algebraic(self) -> str:
        """Convert to algebraic notation (e.g., 'e4')."""
        return f"{chr(ord('a') + self.col)}{self.row + 1}"

    @staticmethod
    def from_algebraic(notation: str) -> "Position":
        """Create position from algebraic notation (e.g., 'e4')."""
        col = ord(notation[0]) - ord('a')
        row = int(notation[1]) - 1
        return Position(row, col)


@dataclass
class Piece:
    """Represents a chess piece."""
    piece_type: PieceType
    color: Color
    has_moved: bool = False

    def __str__(self) -> str:
        symbols = {
            (Color.WHITE, PieceType.KING): "♔",
            (Color.WHITE, PieceType.QUEEN): "♕",
            (Color.WHITE, PieceType.ROOK): "♖",
            (Color.WHITE, PieceType.BISHOP): "♗",
            (Color.WHITE, PieceType.KNIGHT): "♘",
            (Color.WHITE, PieceType.PAWN): "♙",
            (Color.BLACK, PieceType.KING): "♚",
            (Color.BLACK, PieceType.QUEEN): "♛",
            (Color.BLACK, PieceType.ROOK): "♜",
            (Color.BLACK, PieceType.BISHOP): "♝",
            (Color.BLACK, PieceType.KNIGHT): "♞",
            (Color.BLACK, PieceType.PAWN): "♟",
        }
        return symbols[(self.color, self.piece_type)]


@dataclass
class Move:
    """Represents a chess move."""
    from_pos: Position
    to_pos: Position
    piece: Piece
    captured_piece: Optional[Piece] = None
    is_castling: bool = False
    is_en_passant: bool = False
    promotion_piece_type: Optional[PieceType] = None


class ChessGame:
    """
    A chess game implementation with flexible piece movement.

    This design uses a strategy where piece movement rules are defined
    in separate methods, making it easy to modify piece behavior in the future.
    """

    def __init__(self) -> None:
        self.board: Dict[Position, Piece] = {}
        self.current_turn: Color = Color.WHITE
        self.move_history: List[Move] = []
        self.en_passant_target: Optional[Position] = None
        self._initialize_board()

    def _initialize_board(self) -> None:
        """Set up the initial chess board position."""
        # Set up pawns
        for col in range(8):
            self.board[Position(1, col)] = Piece(PieceType.PAWN, Color.WHITE)
            self.board[Position(6, col)] = Piece(PieceType.PAWN, Color.BLACK)

        # Set up back ranks
        back_rank_order = [
            PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
            PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK
        ]

        for col, piece_type in enumerate(back_rank_order):
            self.board[Position(0, col)] = Piece(piece_type, Color.WHITE)
            self.board[Position(7, col)] = Piece(piece_type, Color.BLACK)

    def get_piece(self, pos: Position) -> Optional[Piece]:
        """Get the piece at a given position."""
        return self.board.get(pos)

    def get_possible_moves(self, from_pos: Position) -> List[Position]:
        """
        Get all possible moves for a piece at the given position.

        This method delegates to piece-specific movement methods,
        making it easy to modify individual piece behaviors later.
        """
        piece = self.get_piece(from_pos)
        if not piece or piece.color != self.current_turn:
            return []

        # Get pseudo-legal moves (moves that don't consider check)
        if piece.piece_type == PieceType.PAWN:
            possible_moves = self._get_pawn_moves(from_pos, piece)
        elif piece.piece_type == PieceType.ROOK:
            possible_moves = self._get_rook_moves(from_pos, piece)
        elif piece.piece_type == PieceType.KNIGHT:
            possible_moves = self._get_knight_moves(from_pos, piece)
        elif piece.piece_type == PieceType.BISHOP:
            possible_moves = self._get_bishop_moves(from_pos, piece)
        elif piece.piece_type == PieceType.QUEEN:
            possible_moves = self._get_queen_moves(from_pos, piece)
        elif piece.piece_type == PieceType.KING:
            possible_moves = self._get_king_moves(from_pos, piece)
        else:
            possible_moves = []

        # Filter out moves that would leave the king in check
        legal_moves = []
        for to_pos in possible_moves:
            if self._is_legal_move(from_pos, to_pos):
                legal_moves.append(to_pos)

        return legal_moves

    def _get_pawn_moves(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get possible moves for a pawn."""
        moves = []
        direction = 1 if piece.color == Color.WHITE else -1

        # Forward move
        forward_pos = from_pos.offset(direction, 0)
        if forward_pos.is_valid() and not self.get_piece(forward_pos):
            moves.append(forward_pos)

            # Double move from starting position
            if not piece.has_moved:
                double_forward = from_pos.offset(2 * direction, 0)
                if double_forward.is_valid() and not self.get_piece(double_forward):
                    moves.append(double_forward)

        # Captures
        for col_offset in [-1, 1]:
            capture_pos = from_pos.offset(direction, col_offset)
            if capture_pos.is_valid():
                target_piece = self.get_piece(capture_pos)
                if target_piece and target_piece.color != piece.color:
                    moves.append(capture_pos)

                # En passant
                if capture_pos == self.en_passant_target:
                    moves.append(capture_pos)

        return moves

    def _get_rook_moves(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get possible moves for a rook."""
        return self._get_sliding_moves(from_pos, piece, [(0, 1), (0, -1), (1, 0), (-1, 0)])

    def _get_bishop_moves(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get possible moves for a bishop."""
        return self._get_sliding_moves(from_pos, piece, [(1, 1), (1, -1), (-1, 1), (-1, -1)])

    def _get_queen_moves(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get possible moves for a queen."""
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        return self._get_sliding_moves(from_pos, piece, directions)

    def _get_knight_moves(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get possible moves for a knight."""
        moves = []
        knight_offsets = [
            (2, 1), (2, -1), (-2, 1), (-2, -1),
            (1, 2), (1, -2), (-1, 2), (-1, -2)
        ]

        for row_offset, col_offset in knight_offsets:
            to_pos = from_pos.offset(row_offset, col_offset)
            if to_pos.is_valid():
                target_piece = self.get_piece(to_pos)
                if not target_piece or target_piece.color != piece.color:
                    moves.append(to_pos)

        return moves

    def _get_king_moves(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get possible moves for a king, including castling."""
        moves = []

        # Regular king moves (one square in any direction)
        for row_offset in [-1, 0, 1]:
            for col_offset in [-1, 0, 1]:
                if row_offset == 0 and col_offset == 0:
                    continue
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    target_piece = self.get_piece(to_pos)
                    if not target_piece or target_piece.color != piece.color:
                        moves.append(to_pos)

        # Castling
        if not piece.has_moved and not self.is_in_check(piece.color):
            # Kingside castling
            kingside_rook_pos = Position(from_pos.row, 7)
            kingside_rook = self.get_piece(kingside_rook_pos)
            if (kingside_rook and
                kingside_rook.piece_type == PieceType.ROOK and
                not kingside_rook.has_moved):
                # Check if squares between king and rook are empty
                if all(not self.get_piece(Position(from_pos.row, col))
                       for col in range(from_pos.col + 1, 7)):
                    # Check if king doesn't pass through check
                    squares_to_check = [from_pos.offset(0, 1), from_pos.offset(0, 2)]
                    if all(not self._is_position_under_attack(pos, piece.color)
                           for pos in squares_to_check):
                        moves.append(from_pos.offset(0, 2))

            # Queenside castling
            queenside_rook_pos = Position(from_pos.row, 0)
            queenside_rook = self.get_piece(queenside_rook_pos)
            if (queenside_rook and
                queenside_rook.piece_type == PieceType.ROOK and
                not queenside_rook.has_moved):
                # Check if squares between king and rook are empty
                if all(not self.get_piece(Position(from_pos.row, col))
                       for col in range(1, from_pos.col)):
                    # Check if king doesn't pass through check
                    squares_to_check = [from_pos.offset(0, -1), from_pos.offset(0, -2)]
                    if all(not self._is_position_under_attack(pos, piece.color)
                           for pos in squares_to_check):
                        moves.append(from_pos.offset(0, -2))

        return moves

    def _get_sliding_moves(
        self,
        from_pos: Position,
        piece: Piece,
        directions: List[Tuple[int, int]]
    ) -> List[Position]:
        """
        Get moves for sliding pieces (rook, bishop, queen).

        This helper method makes it easy to change how sliding pieces move
        by simply modifying the directions parameter.
        """
        moves = []

        for row_delta, col_delta in directions:
            current_pos = from_pos
            while True:
                current_pos = current_pos.offset(row_delta, col_delta)
                if not current_pos.is_valid():
                    break

                target_piece = self.get_piece(current_pos)
                if not target_piece:
                    moves.append(current_pos)
                elif target_piece.color != piece.color:
                    moves.append(current_pos)
                    break
                else:
                    break

        return moves

    def _is_legal_move(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if a move is legal (doesn't leave king in check)."""
        # Make the move temporarily
        original_board = deepcopy(self.board)
        original_en_passant = self.en_passant_target

        self._execute_move_on_board(from_pos, to_pos)

        # Check if king is in check after the move
        piece = self.get_piece(to_pos)
        is_legal = piece is not None and not self.is_in_check(piece.color)

        # Restore board
        self.board = original_board
        self.en_passant_target = original_en_passant

        return is_legal

    def _execute_move_on_board(self, from_pos: Position, to_pos: Position) -> None:
        """Execute a move on the board without validation."""
        piece = self.get_piece(from_pos)
        if not piece:
            return

        # Handle en passant capture
        if (piece.piece_type == PieceType.PAWN and
            to_pos == self.en_passant_target and
            self.en_passant_target is not None):
            # Remove the captured pawn
            direction = 1 if piece.color == Color.WHITE else -1
            captured_pawn_pos = to_pos.offset(-direction, 0)
            if captured_pawn_pos in self.board:
                del self.board[captured_pawn_pos]

        # Handle castling
        if piece.piece_type == PieceType.KING:
            col_diff = to_pos.col - from_pos.col
            if abs(col_diff) == 2:
                # Move the rook
                if col_diff > 0:  # Kingside
                    rook_from = Position(from_pos.row, 7)
                    rook_to = Position(from_pos.row, 5)
                else:  # Queenside
                    rook_from = Position(from_pos.row, 0)
                    rook_to = Position(from_pos.row, 3)

                rook = self.board.get(rook_from)
                if rook:
                    self.board[rook_to] = rook
                    del self.board[rook_from]

        # Move the piece
        self.board[to_pos] = piece
        del self.board[from_pos]

    def make_move(
        self,
        from_pos: Position,
        to_pos: Position,
        promotion_piece_type: Optional[PieceType] = None
    ) -> bool:
        """
        Make a move on the board.

        Returns True if the move was successful, False otherwise.
        """
        piece = self.get_piece(from_pos)
        if not piece or piece.color != self.current_turn:
            return False

        # Check if the move is in the list of possible moves
        possible_moves = self.get_possible_moves(from_pos)
        if to_pos not in possible_moves:
            return False

        # Create move record
        captured_piece = self.get_piece(to_pos)
        is_castling = (piece.piece_type == PieceType.KING and
                      abs(to_pos.col - from_pos.col) == 2)
        is_en_passant = (piece.piece_type == PieceType.PAWN and
                        to_pos == self.en_passant_target and
                        self.en_passant_target is not None)

        if is_en_passant:
            direction = 1 if piece.color == Color.WHITE else -1
            captured_pawn_pos = to_pos.offset(-direction, 0)
            captured_piece = self.get_piece(captured_pawn_pos)

        move = Move(
            from_pos=from_pos,
            to_pos=to_pos,
            piece=piece,
            captured_piece=captured_piece,
            is_castling=is_castling,
            is_en_passant=is_en_passant,
            promotion_piece_type=promotion_piece_type
        )

        # Execute the move
        self._execute_move_on_board(from_pos, to_pos)

        # Handle pawn promotion
        if piece.piece_type == PieceType.PAWN:
            promotion_row = 7 if piece.color == Color.WHITE else 0
            if to_pos.row == promotion_row:
                if promotion_piece_type is None:
                    promotion_piece_type = PieceType.QUEEN
                self.board[to_pos] = Piece(promotion_piece_type, piece.color, has_moved=True)

        # Update en passant target
        self.en_passant_target = None
        if piece.piece_type == PieceType.PAWN:
            if abs(to_pos.row - from_pos.row) == 2:
                direction = 1 if piece.color == Color.WHITE else -1
                self.en_passant_target = from_pos.offset(direction, 0)

        # Mark piece as moved
        moved_piece = self.get_piece(to_pos)
        if moved_piece:
            moved_piece.has_moved = True

        # Record move and switch turns
        self.move_history.append(move)
        self.current_turn = self.current_turn.opposite()

        return True

    def is_in_check(self, color: Color) -> bool:
        """Check if the king of the given color is in check."""
        # Find the king
        king_pos = None
        for pos, piece in self.board.items():
            if piece.piece_type == PieceType.KING and piece.color == color:
                king_pos = pos
                break

        if king_pos is None:
            return False

        return self._is_position_under_attack(king_pos, color)

    def _is_position_under_attack(self, pos: Position, by_color: Color) -> bool:
        """Check if a position is under attack by the opponent."""
        opponent_color = by_color.opposite()

        # Check for attacks from each opponent piece
        for piece_pos, piece in self.board.items():
            if piece.color != opponent_color:
                continue

            # Get attacking moves for this piece (without recursively checking for check)
            if piece.piece_type == PieceType.PAWN:
                attacking_moves = self._get_pawn_attacking_squares(piece_pos, piece)
            elif piece.piece_type == PieceType.KNIGHT:
                attacking_moves = self._get_knight_moves(piece_pos, piece)
            elif piece.piece_type == PieceType.BISHOP:
                attacking_moves = self._get_bishop_moves(piece_pos, piece)
            elif piece.piece_type == PieceType.ROOK:
                attacking_moves = self._get_rook_moves(piece_pos, piece)
            elif piece.piece_type == PieceType.QUEEN:
                attacking_moves = self._get_queen_moves(piece_pos, piece)
            elif piece.piece_type == PieceType.KING:
                attacking_moves = self._get_king_attacking_squares(piece_pos, piece)
            else:
                attacking_moves = []

            if pos in attacking_moves:
                return True

        return False

    def _get_pawn_attacking_squares(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get squares that a pawn is attacking (diagonal squares only)."""
        direction = 1 if piece.color == Color.WHITE else -1
        attacking_squares = []

        for col_offset in [-1, 1]:
            attack_pos = from_pos.offset(direction, col_offset)
            if attack_pos.is_valid():
                attacking_squares.append(attack_pos)

        return attacking_squares

    def _get_king_attacking_squares(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get squares that a king is attacking (all adjacent squares)."""
        attacking_squares = []

        for row_offset in [-1, 0, 1]:
            for col_offset in [-1, 0, 1]:
                if row_offset == 0 and col_offset == 0:
                    continue
                attack_pos = from_pos.offset(row_offset, col_offset)
                if attack_pos.is_valid():
                    attacking_squares.append(attack_pos)

        return attacking_squares

    def is_checkmate(self) -> bool:
        """Check if the current player is in checkmate."""
        if not self.is_in_check(self.current_turn):
            return False

        # Check if any legal move exists
        # Use list() to create a snapshot to avoid "dictionary changed during iteration"
        for pos, piece in list(self.board.items()):
            if piece.color == self.current_turn:
                if len(self.get_possible_moves(pos)) > 0:
                    return False

        return True

    def is_stalemate(self) -> bool:
        """Check if the game is in stalemate."""
        if self.is_in_check(self.current_turn):
            return False

        # Check if any legal move exists
        # Use list() to create a snapshot to avoid "dictionary changed during iteration"
        for pos, piece in list(self.board.items()):
            if piece.color == self.current_turn:
                if len(self.get_possible_moves(pos)) > 0:
                    return False

        return True

    def is_game_over(self) -> bool:
        """Check if the game is over."""
        return self.is_checkmate() or self.is_stalemate()

    def get_game_result(self) -> Optional[str]:
        """Get the result of the game."""
        if self.is_checkmate():
            winner = self.current_turn.opposite()
            return f"{winner.value} wins by checkmate"
        elif self.is_stalemate():
            return "Draw by stalemate"
        return None

    def display_board(self) -> str:
        """Return a string representation of the board."""
        lines = []
        lines.append("  a b c d e f g h")
        for row in range(7, -1, -1):
            line = f"{row + 1} "
            for col in range(8):
                piece = self.get_piece(Position(row, col))
                if piece:
                    line += str(piece) + " "
                else:
                    line += ". "
            line += f"{row + 1}"
            lines.append(line)
        lines.append("  a b c d e f g h")
        return "\n".join(lines)
