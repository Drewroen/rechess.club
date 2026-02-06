import pytest
from chess_game import (
    ChessGame, Position, Piece, PieceType, Color, Move
)


class TestPosition:
    """Test suite for Position class."""

    @pytest.mark.parametrize("row,col,expected", [
        (0, 0, True),
        (7, 7, True),
        (3, 4, True),
        (-1, 0, False),
        (0, -1, False),
        (8, 0, False),
        (0, 8, False),
        (10, 10, False),
    ])
    def test_is_valid(self, row, col, expected):
        """Test position validation with various coordinates."""
        pos = Position(row, col)
        assert pos.is_valid() == expected

    @pytest.mark.parametrize("row,col,row_delta,col_delta,expected_row,expected_col", [
        (3, 3, 1, 0, 4, 3),
        (3, 3, 0, 1, 3, 4),
        (3, 3, -1, -1, 2, 2),
        (0, 0, 2, 2, 2, 2),
    ])
    def test_offset(self, row, col, row_delta, col_delta, expected_row, expected_col):
        """Test position offset calculation."""
        pos = Position(row, col)
        new_pos = pos.offset(row_delta, col_delta)
        assert new_pos.row == expected_row
        assert new_pos.col == expected_col

    @pytest.mark.parametrize("row,col,expected", [
        (0, 0, "a1"),
        (0, 7, "h1"),
        (7, 0, "a8"),
        (7, 7, "h8"),
        (3, 4, "e4"),
        (1, 2, "c2"),
    ])
    def test_to_algebraic(self, row, col, expected):
        """Test conversion to algebraic notation."""
        pos = Position(row, col)
        assert pos.to_algebraic() == expected

    @pytest.mark.parametrize("notation,expected_row,expected_col", [
        ("a1", 0, 0),
        ("h1", 0, 7),
        ("a8", 7, 0),
        ("h8", 7, 7),
        ("e4", 3, 4),
        ("c2", 1, 2),
    ])
    def test_from_algebraic(self, notation, expected_row, expected_col):
        """Test creation from algebraic notation."""
        pos = Position.from_algebraic(notation)
        assert pos.row == expected_row
        assert pos.col == expected_col


class TestColor:
    """Test suite for Color enum."""

    @pytest.mark.parametrize("color,expected_opposite", [
        (Color.WHITE, Color.BLACK),
        (Color.BLACK, Color.WHITE),
    ])
    def test_opposite(self, color, expected_opposite):
        """Test color opposite method."""
        assert color.opposite() == expected_opposite


class TestChessGameInitialization:
    """Test suite for chess game initialization."""

    def test_initial_board_setup(self):
        """Test that the board is set up correctly."""
        game = ChessGame()

        # Check white pawns
        for col in range(8):
            piece = game.get_piece(Position(1, col))
            assert piece is not None
            assert piece.piece_type == PieceType.PAWN
            assert piece.color == Color.WHITE

        # Check black pawns
        for col in range(8):
            piece = game.get_piece(Position(6, col))
            assert piece is not None
            assert piece.piece_type == PieceType.PAWN
            assert piece.color == Color.BLACK

    @pytest.mark.parametrize("row,col,piece_type,color", [
        (0, 0, PieceType.ROOK, Color.WHITE),
        (0, 1, PieceType.KNIGHT, Color.WHITE),
        (0, 2, PieceType.BISHOP, Color.WHITE),
        (0, 3, PieceType.QUEEN, Color.WHITE),
        (0, 4, PieceType.KING, Color.WHITE),
        (0, 5, PieceType.BISHOP, Color.WHITE),
        (0, 6, PieceType.KNIGHT, Color.WHITE),
        (0, 7, PieceType.ROOK, Color.WHITE),
        (7, 0, PieceType.ROOK, Color.BLACK),
        (7, 1, PieceType.KNIGHT, Color.BLACK),
        (7, 2, PieceType.BISHOP, Color.BLACK),
        (7, 3, PieceType.QUEEN, Color.BLACK),
        (7, 4, PieceType.KING, Color.BLACK),
        (7, 5, PieceType.BISHOP, Color.BLACK),
        (7, 6, PieceType.KNIGHT, Color.BLACK),
        (7, 7, PieceType.ROOK, Color.BLACK),
    ])
    def test_initial_back_rank_pieces(self, row, col, piece_type, color):
        """Test that back rank pieces are set up correctly."""
        game = ChessGame()
        piece = game.get_piece(Position(row, col))
        assert piece is not None
        assert piece.piece_type == piece_type
        assert piece.color == color

    def test_initial_turn(self):
        """Test that white starts first."""
        game = ChessGame()
        assert game.current_turn == Color.WHITE

    def test_empty_squares(self):
        """Test that middle squares are empty initially."""
        game = ChessGame()
        for row in range(2, 6):
            for col in range(8):
                assert game.get_piece(Position(row, col)) is None


class TestPawnMoves:
    """Test suite for pawn movement."""

    @pytest.mark.parametrize("from_notation,expected_moves", [
        ("e2", ["e3", "e4"]),
        ("d2", ["d3", "d4"]),
        ("a2", ["a3", "a4"]),
        ("h2", ["h3", "h4"]),
    ])
    def test_pawn_initial_double_move(self, from_notation, expected_moves):
        """Test pawn can move one or two squares from starting position."""
        game = ChessGame()
        from_pos = Position.from_algebraic(from_notation)
        moves = game.get_possible_moves(from_pos)
        move_notations = [pos.to_algebraic() for pos in moves]
        assert sorted(move_notations) == sorted(expected_moves)

    def test_pawn_single_move_after_first_move(self):
        """Test pawn can only move one square after initial move."""
        game = ChessGame()
        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        game.make_move(Position.from_algebraic("d7"), Position.from_algebraic("d6"))

        # White pawn should only be able to move one square forward
        moves = game.get_possible_moves(Position.from_algebraic("e4"))
        assert len(moves) == 1
        assert Position.from_algebraic("e5") in moves

    def test_pawn_blocked_by_piece(self):
        """Test pawn cannot move through pieces."""
        game = ChessGame()
        # Move white pawn
        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        # Move black pawn to block
        game.make_move(Position.from_algebraic("e7"), Position.from_algebraic("e5"))

        # White pawn should have no moves (blocked)
        moves = game.get_possible_moves(Position.from_algebraic("e4"))
        assert len(moves) == 0

    @pytest.mark.parametrize("setup_moves,pawn_pos,expected_captures", [
        # White pawn capturing black pieces
        ([("e2", "e4"), ("d7", "d5"), ("e4", "e5"), ("d5", "d4")], "e5", ["d6"]),
    ])
    def test_pawn_captures(self, setup_moves, pawn_pos, expected_captures):
        """Test pawn diagonal capture moves."""
        game = ChessGame()
        for from_notation, to_notation in setup_moves:
            game.make_move(Position.from_algebraic(from_notation),
                          Position.from_algebraic(to_notation))

        # Add a piece for pawn to capture
        game.board[Position.from_algebraic("d6")] = Piece(PieceType.PAWN, Color.BLACK)

        moves = game.get_possible_moves(Position.from_algebraic(pawn_pos))
        capture_moves = [pos.to_algebraic() for pos in moves if pos.to_algebraic() in expected_captures]
        assert len(capture_moves) == len(expected_captures)

    def test_pawn_en_passant(self):
        """Test en passant capture."""
        game = ChessGame()
        # Set up en passant scenario
        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        game.make_move(Position.from_algebraic("a7"), Position.from_algebraic("a6"))
        game.make_move(Position.from_algebraic("e4"), Position.from_algebraic("e5"))
        game.make_move(Position.from_algebraic("d7"), Position.from_algebraic("d5"))

        # Check en passant is possible
        moves = game.get_possible_moves(Position.from_algebraic("e5"))
        assert Position.from_algebraic("d6") in moves


class TestKnightMoves:
    """Test suite for knight movement."""

    def test_knight_initial_moves(self):
        """Test knight moves from starting position."""
        game = ChessGame()
        moves = game.get_possible_moves(Position.from_algebraic("b1"))
        move_notations = [pos.to_algebraic() for pos in moves]
        assert sorted(move_notations) == sorted(["a3", "c3"])

    @pytest.mark.parametrize("knight_pos,expected_moves", [
        ("d4", ["b3", "b5", "c2", "c6", "e2", "e6", "f3", "f5"]),
        ("a1", ["b3", "c2"]),
        ("h1", ["f2", "g3"]),
        ("e4", ["c3", "c5", "d2", "d6", "f2", "f6", "g3", "g5"]),
    ])
    def test_knight_moves_from_various_positions(self, knight_pos, expected_moves):
        """Test knight L-shaped moves from various positions."""
        game = ChessGame()
        # Clear board and place knight
        game.board.clear()
        game.board[Position.from_algebraic(knight_pos)] = Piece(PieceType.KNIGHT, Color.WHITE)

        moves = game.get_possible_moves(Position.from_algebraic(knight_pos))
        move_notations = sorted([pos.to_algebraic() for pos in moves])
        assert move_notations == sorted(expected_moves)


class TestRookMoves:
    """Test suite for rook movement."""

    @pytest.mark.parametrize("rook_pos,blocked_squares,expected_move_count", [
        ("d4", [], 14),  # Rook in center with no blockers
        ("a1", [], 14),  # Rook in corner
        ("d4", ["d6", "d2", "f4", "b4"], 4),  # Blocked in all directions
    ])
    def test_rook_moves(self, rook_pos, blocked_squares, expected_move_count):
        """Test rook horizontal and vertical moves."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic(rook_pos)] = Piece(PieceType.ROOK, Color.WHITE)

        # Add blocking pieces
        for square in blocked_squares:
            game.board[Position.from_algebraic(square)] = Piece(PieceType.PAWN, Color.WHITE)

        moves = game.get_possible_moves(Position.from_algebraic(rook_pos))
        assert len(moves) == expected_move_count


class TestBishopMoves:
    """Test suite for bishop movement."""

    @pytest.mark.parametrize("bishop_pos,expected_move_count", [
        ("d4", 13),  # Bishop in center
        ("a1", 7),   # Bishop in corner
        ("h1", 7),   # Bishop in corner
        ("d1", 7),   # Bishop on edge
    ])
    def test_bishop_diagonal_moves(self, bishop_pos, expected_move_count):
        """Test bishop diagonal moves from various positions."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic(bishop_pos)] = Piece(PieceType.BISHOP, Color.WHITE)

        moves = game.get_possible_moves(Position.from_algebraic(bishop_pos))
        assert len(moves) == expected_move_count


class TestQueenMoves:
    """Test suite for queen movement."""

    @pytest.mark.parametrize("queen_pos,expected_move_count", [
        ("d4", 27),  # Queen in center (14 straight + 13 diagonal)
        ("a1", 21),  # Queen in corner (14 straight + 7 diagonal)
        ("e4", 27),  # Queen in center
    ])
    def test_queen_moves(self, queen_pos, expected_move_count):
        """Test queen moves (combination of rook and bishop)."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic(queen_pos)] = Piece(PieceType.QUEEN, Color.WHITE)

        moves = game.get_possible_moves(Position.from_algebraic(queen_pos))
        assert len(moves) == expected_move_count


class TestKingMoves:
    """Test suite for king movement."""

    @pytest.mark.parametrize("king_pos,expected_moves", [
        ("e4", ["d3", "d4", "d5", "e3", "e5", "f3", "f4", "f5"]),
        ("a1", ["a2", "b1", "b2"]),
        ("h8", ["g7", "g8", "h7"]),
    ])
    def test_king_basic_moves(self, king_pos, expected_moves):
        """Test king moves one square in any direction."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic(king_pos)] = Piece(PieceType.KING, Color.WHITE)

        moves = game.get_possible_moves(Position.from_algebraic(king_pos))
        move_notations = sorted([pos.to_algebraic() for pos in moves])
        assert move_notations == sorted(expected_moves)

    def test_kingside_castling_white(self):
        """Test white kingside castling."""
        game = ChessGame()
        # Clear squares between king and rook
        game.board.pop(Position.from_algebraic("f1"))
        game.board.pop(Position.from_algebraic("g1"))

        moves = game.get_possible_moves(Position.from_algebraic("e1"))
        assert Position.from_algebraic("g1") in moves

    def test_queenside_castling_white(self):
        """Test white queenside castling."""
        game = ChessGame()
        # Clear squares between king and rook
        game.board.pop(Position.from_algebraic("d1"))
        game.board.pop(Position.from_algebraic("c1"))
        game.board.pop(Position.from_algebraic("b1"))

        moves = game.get_possible_moves(Position.from_algebraic("e1"))
        assert Position.from_algebraic("c1") in moves

    def test_castling_blocked_by_piece(self):
        """Test castling is blocked by piece between king and rook."""
        game = ChessGame()
        # f1 is occupied (knight is still there)
        moves = game.get_possible_moves(Position.from_algebraic("e1"))
        assert Position.from_algebraic("g1") not in moves

    def test_cannot_castle_after_king_moves(self):
        """Test castling is not allowed after king has moved."""
        game = ChessGame()
        # Clear squares
        game.board.pop(Position.from_algebraic("f1"))
        game.board.pop(Position.from_algebraic("g1"))

        # Move king and move it back
        game.make_move(Position.from_algebraic("e1"), Position.from_algebraic("f1"))
        game.make_move(Position.from_algebraic("e7"), Position.from_algebraic("e6"))
        game.make_move(Position.from_algebraic("f1"), Position.from_algebraic("e1"))
        game.make_move(Position.from_algebraic("e6"), Position.from_algebraic("e5"))

        # Castling should not be available
        moves = game.get_possible_moves(Position.from_algebraic("e1"))
        assert Position.from_algebraic("g1") not in moves


class TestCheckAndCheckmate:
    """Test suite for check and checkmate detection."""

    def test_is_in_check(self):
        """Test check detection."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("e8")] = Piece(PieceType.ROOK, Color.BLACK)

        assert game.is_in_check(Color.WHITE)
        assert not game.is_in_check(Color.BLACK)

    def test_cannot_move_into_check(self):
        """Test that king cannot move into check."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic("e4")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("e7")] = Piece(PieceType.ROOK, Color.BLACK)

        moves = game.get_possible_moves(Position.from_algebraic("e4"))
        # King should not be able to move to e5 (into rook's path)
        assert Position.from_algebraic("e5") not in moves

    def test_back_rank_checkmate(self):
        """Test detection of back rank checkmate."""
        game = ChessGame()
        game.board.clear()
        # Set up two rook checkmate: King trapped in corner
        game.board[Position.from_algebraic("h8")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("a7")] = Piece(PieceType.ROOK, Color.BLACK)
        game.board[Position.from_algebraic("b8")] = Piece(PieceType.ROOK, Color.BLACK)
        game.board[Position.from_algebraic("f6")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        assert game.is_checkmate()

    def test_stalemate_detection(self):
        """Test stalemate detection."""
        game = ChessGame()
        game.board.clear()
        # Set up stalemate position
        game.board[Position.from_algebraic("a8")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("c7")] = Piece(PieceType.QUEEN, Color.BLACK)
        game.board[Position.from_algebraic("b6")] = Piece(PieceType.KING, Color.BLACK)

        # Move black king away to create stalemate for white
        game.board[Position.from_algebraic("b6")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        assert game.is_stalemate()


class TestMoveExecution:
    """Test suite for move execution and game state."""

    @pytest.mark.parametrize("from_square,to_square,should_succeed", [
        ("e2", "e4", True),
        ("e2", "e5", False),  # Invalid move
        ("e7", "e5", False),  # Wrong color
        ("d1", "d3", False),  # Queen blocked by pawn
    ])
    def test_make_move_validation(self, from_square, to_square, should_succeed):
        """Test move validation in make_move method."""
        game = ChessGame()
        result = game.make_move(
            Position.from_algebraic(from_square),
            Position.from_algebraic(to_square)
        )
        assert result == should_succeed

    def test_turn_switching(self):
        """Test that turns switch after valid moves."""
        game = ChessGame()
        assert game.current_turn == Color.WHITE

        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        assert game.current_turn == Color.BLACK

        game.make_move(Position.from_algebraic("e7"), Position.from_algebraic("e5"))
        assert game.current_turn == Color.WHITE

    def test_move_history(self):
        """Test that moves are recorded in history."""
        game = ChessGame()
        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        game.make_move(Position.from_algebraic("e7"), Position.from_algebraic("e5"))

        assert len(game.move_history) == 2
        assert game.move_history[0].from_pos == Position.from_algebraic("e2")
        assert game.move_history[0].to_pos == Position.from_algebraic("e4")

    def test_piece_has_moved_flag(self):
        """Test that has_moved flag is set after moving."""
        game = ChessGame()
        piece = game.get_piece(Position.from_algebraic("e2"))
        assert piece is not None
        assert not piece.has_moved

        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        moved_piece = game.get_piece(Position.from_algebraic("e4"))
        assert moved_piece is not None
        assert moved_piece.has_moved


class TestPawnPromotion:
    """Test suite for pawn promotion."""

    @pytest.mark.parametrize("promotion_type,expected_type", [
        (PieceType.QUEEN, PieceType.QUEEN),
        (PieceType.ROOK, PieceType.ROOK),
        (PieceType.BISHOP, PieceType.BISHOP),
        (PieceType.KNIGHT, PieceType.KNIGHT),
    ])
    def test_pawn_promotion(self, promotion_type, expected_type):
        """Test pawn promotion to different piece types."""
        game = ChessGame()
        game.board.clear()
        # Set up white pawn about to promote
        game.board[Position.from_algebraic("e7")] = Piece(PieceType.PAWN, Color.WHITE, has_moved=True)
        game.current_turn = Color.WHITE

        game.make_move(
            Position.from_algebraic("e7"),
            Position.from_algebraic("e8"),
            promotion_piece_type=promotion_type
        )

        promoted_piece = game.get_piece(Position.from_algebraic("e8"))
        assert promoted_piece is not None
        assert promoted_piece.piece_type == expected_type
        assert promoted_piece.color == Color.WHITE

    def test_automatic_queen_promotion(self):
        """Test that pawn promotes to queen by default."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic("e7")] = Piece(PieceType.PAWN, Color.WHITE, has_moved=True)
        game.current_turn = Color.WHITE

        game.make_move(Position.from_algebraic("e7"), Position.from_algebraic("e8"))

        promoted_piece = game.get_piece(Position.from_algebraic("e8"))
        assert promoted_piece is not None
        assert promoted_piece.piece_type == PieceType.QUEEN


class TestCastling:
    """Test suite for castling moves."""

    def test_castling_moves_rook(self):
        """Test that castling moves the rook correctly."""
        game = ChessGame()
        # Clear squares for kingside castling
        game.board.pop(Position.from_algebraic("f1"))
        game.board.pop(Position.from_algebraic("g1"))

        game.make_move(Position.from_algebraic("e1"), Position.from_algebraic("g1"))

        # Check king and rook positions
        king_piece = game.get_piece(Position.from_algebraic("g1"))
        assert king_piece is not None
        assert king_piece.piece_type == PieceType.KING
        rook_piece = game.get_piece(Position.from_algebraic("f1"))
        assert rook_piece is not None
        assert rook_piece.piece_type == PieceType.ROOK
        assert game.get_piece(Position.from_algebraic("h1")) is None

    def test_queenside_castling_moves_rook(self):
        """Test that queenside castling moves the rook correctly."""
        game = ChessGame()
        # Clear squares for queenside castling
        game.board.pop(Position.from_algebraic("d1"))
        game.board.pop(Position.from_algebraic("c1"))
        game.board.pop(Position.from_algebraic("b1"))

        game.make_move(Position.from_algebraic("e1"), Position.from_algebraic("c1"))

        # Check king and rook positions
        king_piece = game.get_piece(Position.from_algebraic("c1"))
        assert king_piece is not None
        assert king_piece.piece_type == PieceType.KING
        rook_piece = game.get_piece(Position.from_algebraic("d1"))
        assert rook_piece is not None
        assert rook_piece.piece_type == PieceType.ROOK
        assert game.get_piece(Position.from_algebraic("a1")) is None


class TestGameState:
    """Test suite for game state methods."""

    def test_is_game_over_initial(self):
        """Test that game is not over at start."""
        game = ChessGame()
        assert not game.is_game_over()

    def test_get_game_result_checkmate(self):
        """Test game result for checkmate."""
        game = ChessGame()
        game.board.clear()
        # Set up two rook checkmate: King trapped in corner
        game.board[Position.from_algebraic("h8")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("a7")] = Piece(PieceType.ROOK, Color.BLACK)
        game.board[Position.from_algebraic("b8")] = Piece(PieceType.ROOK, Color.BLACK)
        game.board[Position.from_algebraic("f6")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        result = game.get_game_result()
        assert result is not None
        assert "black wins by checkmate" in result.lower()

    def test_get_game_result_stalemate(self):
        """Test game result for stalemate."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic("a8")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("c7")] = Piece(PieceType.QUEEN, Color.BLACK)
        game.board[Position.from_algebraic("b6")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        result = game.get_game_result()
        assert result is not None
        assert "stalemate" in result.lower()

    def test_get_game_result_ongoing(self):
        """Test game result returns None for ongoing game."""
        game = ChessGame()
        assert game.get_game_result() is None


class TestPromotedPieceMoves:
    """Test suite for moves of promoted pieces."""

    def test_promoted_queen_has_queen_moves(self):
        """Test that a promoted queen can move like a queen."""
        game = ChessGame()
        game.board.clear()
        # Set up white pawn about to promote
        game.board[Position.from_algebraic("e7")] = Piece(PieceType.PAWN, Color.WHITE, has_moved=True)
        game.current_turn = Color.WHITE

        # Promote pawn to queen
        game.make_move(
            Position.from_algebraic("e7"),
            Position.from_algebraic("e8"),
            promotion_piece_type=PieceType.QUEEN
        )

        # Verify the piece is actually a queen now
        promoted_piece = game.get_piece(Position.from_algebraic("e8"))
        assert promoted_piece is not None
        assert promoted_piece.piece_type == PieceType.QUEEN, f"Expected QUEEN but got {promoted_piece.piece_type}"

        # Switch back to white's turn to test the promoted queen
        game.current_turn = Color.WHITE

        # Check that the promoted queen has queen moves
        moves = game.get_possible_moves(Position.from_algebraic("e8"))

        # A queen on e8 should have many moves available
        # At minimum, it should be able to move to e7, e6, d8, f8, etc.
        assert len(moves) > 0, "Promoted queen should have moves available"

        # Specifically check for some expected queen moves
        assert Position.from_algebraic("e7") in moves, "Queen should be able to move to e7"
        assert Position.from_algebraic("e1") in moves, "Queen should be able to move to e1"
        assert Position.from_algebraic("a8") in moves, "Queen should be able to move to a8"
        assert Position.from_algebraic("h8") in moves, "Queen should be able to move to h8"

    def test_promoted_piece_moves_after_full_game_sequence(self):
        """Test that a promoted piece can move after a realistic game sequence."""
        game = ChessGame()

        # Move a white pawn from starting position to promotion (simpler approach)
        # Clear the board and set up a scenario where white can promote
        game.board.clear()
        game.board[Position.from_algebraic("a7")] = Piece(PieceType.PAWN, Color.WHITE, has_moved=True)
        game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("e8")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        # Promote the pawn
        assert game.make_move(Position.from_algebraic("a7"), Position.from_algebraic("a8"))

        # Verify the piece is a queen
        promoted_piece = game.get_piece(Position.from_algebraic("a8"))
        assert promoted_piece is not None
        assert promoted_piece.piece_type == PieceType.QUEEN, f"Expected QUEEN but got {promoted_piece.piece_type}"

        # It's now black's turn, so let black make a move (just move the king)
        assert game.make_move(Position.from_algebraic("e8"), Position.from_algebraic("e7"))

        # Now it's white's turn again - the promoted queen should be able to move
        moves = game.get_possible_moves(Position.from_algebraic("a8"))
        assert len(moves) > 0, "Promoted queen should have moves available on next turn"

        # Verify queen can actually move
        assert game.make_move(Position.from_algebraic("a8"), Position.from_algebraic("a7")), "Queen should be able to move"

    def test_promoted_piece_with_string_promotion_type_fails(self):
        """Test that promotion with a string instead of PieceType enum causes wrong piece type."""
        game = ChessGame()
        game.board.clear()
        game.board[Position.from_algebraic("a7")] = Piece(PieceType.PAWN, Color.WHITE, has_moved=True)
        game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("e8")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        # Try to promote with a string (simulating incorrect usage)
        # This demonstrates the bug - when string is passed instead of enum
        assert game.make_move(Position.from_algebraic("a7"), Position.from_algebraic("a8"), promotion_piece_type="queen")

        # The piece will be created with string type instead of enum
        promoted_piece = game.get_piece(Position.from_algebraic("a8"))
        assert promoted_piece is not None
        # This shows the bug - piece_type is a string, not an enum
        assert promoted_piece.piece_type == "queen", f"Bug demonstration: piece type is {promoted_piece.piece_type}"
        assert promoted_piece.piece_type != PieceType.QUEEN, "This shows the bug - types don't match"

        # Because piece_type is a string, it won't match any enum checks in get_possible_moves
        game.current_turn = Color.WHITE
        moves = game.get_possible_moves(Position.from_algebraic("a8"))
        # This is the bug - no moves because piece_type doesn't match any checks
        assert len(moves) == 0, "Bug: promoted piece has no moves because piece_type is a string"
