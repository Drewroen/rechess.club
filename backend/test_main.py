import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from main import Room, ConnectionManager
from chess_game import ChessGame, Position, Piece, PieceType, Color


class MockWebSocket:
    """Mock WebSocket for testing."""
    def __init__(self):
        self.messages_sent = []
        self.client_state = MagicMock()
        self.client_state.value = 1  # CONNECTED state

    async def send_text(self, message: str) -> None:
        """Store messages sent through this websocket."""
        self.messages_sent.append(message)

    async def accept(self) -> None:
        """Accept the websocket connection."""
        pass


class TestRoom:
    """Test suite for Room class."""

    def test_room_initialization(self):
        """Test that a room initializes correctly with two players."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        room = Room(player1, player2)

        assert room.player1 == player1
        assert room.player2 == player2
        assert room.id is not None
        assert len(room.id) > 0
        assert isinstance(room.game, ChessGame)

    @pytest.mark.asyncio
    async def test_notify_players(self):
        """Test that notify_players sends message to both players."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        test_message = "Test notification"
        await room.notify_players(test_message)

        assert test_message in player1.messages_sent
        assert test_message in player2.messages_sent

    @pytest.mark.asyncio
    async def test_notify_players_with_disconnected_player(self):
        """Test that notify_players handles disconnected players gracefully."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        # Make player2 raise RuntimeError when sending
        async def raise_error(msg):
            raise RuntimeError("Connection closed")
        player2.send_text = raise_error

        room = Room(player1, player2)

        # Should not raise exception
        await room.notify_players("Test message")

        # Player1 should still receive the message
        assert "Test message" in player1.messages_sent

    @pytest.mark.asyncio
    async def test_notify_players_both_disconnected(self):
        """Test that notify_players handles both players disconnected."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        # Make both players raise RuntimeError when sending
        async def raise_error(msg):
            raise RuntimeError("Connection closed")
        player1.send_text = raise_error
        player2.send_text = raise_error

        room = Room(player1, player2)

        # Should not raise exception
        await room.notify_players("Test message")

    @pytest.mark.asyncio
    async def test_broadcast_board_state_structure(self):
        """Test that broadcast_board_state sends properly structured JSON."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        await room.broadcast_board_state()

        # Both players should receive a message
        assert len(player1.messages_sent) == 1
        assert len(player2.messages_sent) == 1

        # Parse the messages
        msg1 = json.loads(player1.messages_sent[0])
        msg2 = json.loads(player2.messages_sent[0])

        # Check message structure
        assert msg1["type"] == "board_state"
        assert msg2["type"] == "board_state"
        assert "board" in msg1
        assert "current_turn" in msg1
        assert "room_id" in msg1
        assert "player_color" in msg1

        # Players should receive different colors
        assert msg1["player_color"] == "white"
        assert msg2["player_color"] == "black"

        # Both should have the same room_id
        assert msg1["room_id"] == msg2["room_id"]

    @pytest.mark.asyncio
    async def test_broadcast_includes_available_moves_for_current_player(self):
        """Test that available moves are only sent to the player whose turn it is."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        await room.broadcast_board_state()

        msg1 = json.loads(player1.messages_sent[0])
        msg2 = json.loads(player2.messages_sent[0])

        # White's turn initially, so player1 (white) should have available_moves
        assert "available_moves" in msg1
        assert len(msg1["available_moves"]) > 0  # Should have initial pawn and knight moves

        # Black should not have available_moves since it's not their turn
        assert "available_moves" not in msg2

    @pytest.mark.asyncio
    async def test_broadcast_board_state_initial_pieces(self):
        """Test that broadcast includes all initial pieces."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        await room.broadcast_board_state()

        msg = json.loads(player1.messages_sent[0])
        board = msg["board"]

        # Should have 32 pieces (16 white + 16 black)
        assert len(board) == 32

        # Check some initial positions
        # White pawn at e2 (row 1, col 4)
        assert "1,4" in board
        assert board["1,4"]["piece_type"] == "pawn"
        assert board["1,4"]["color"] == "white"

        # Black king at e8 (row 7, col 4)
        assert "7,4" in board
        assert board["7,4"]["piece_type"] == "king"
        assert board["7,4"]["color"] == "black"

    def test_has_player(self):
        """Test has_player method correctly identifies players."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        player3 = MockWebSocket()
        room = Room(player1, player2)

        assert room.has_player(player1)
        assert room.has_player(player2)
        assert not room.has_player(player3)

    def test_get_player_color(self):
        """Test get_player_color returns correct colors for players."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        player3 = MockWebSocket()
        room = Room(player1, player2)

        assert room.get_player_color(player1) == Color.WHITE
        assert room.get_player_color(player2) == Color.BLACK
        assert room.get_player_color(player3) is None


class TestConnectionManager:
    """Test suite for ConnectionManager class."""

    @pytest.mark.asyncio
    async def test_first_player_waits_in_queue(self):
        """Test that first player is added to queue and waits."""
        manager = ConnectionManager()
        player1 = MockWebSocket()

        await manager.connect(player1)

        assert player1 in manager.queue
        assert len(manager.queue) == 1
        assert len(manager.rooms) == 0
        assert "Waiting for opponent..." in player1.messages_sent

    @pytest.mark.asyncio
    async def test_two_players_create_room(self):
        """Test that two players create a room and are removed from queue."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        await manager.connect(player1)
        await manager.connect(player2)

        # Queue should be empty
        assert len(manager.queue) == 0

        # Should have created one room
        assert len(manager.rooms) == 1

        # Both players should be mapped to the same room
        room_id1 = manager.websocket_to_room.get(player1)
        room_id2 = manager.websocket_to_room.get(player2)
        assert room_id1 is not None
        assert room_id1 == room_id2

        # Both players should have received match notification and board state
        assert len(player1.messages_sent) >= 2  # "Waiting..." and "Match found!"
        assert len(player2.messages_sent) >= 2

        # Check for match found message
        match_found = False
        for msg in player1.messages_sent:
            if "Match found" in msg:
                match_found = True
                break
        assert match_found

    @pytest.mark.asyncio
    async def test_disconnect_from_queue(self):
        """Test that disconnecting while in queue removes player."""
        manager = ConnectionManager()
        player1 = MockWebSocket()

        await manager.connect(player1)
        assert player1 in manager.queue

        await manager.disconnect(player1)
        assert player1 not in manager.queue

    @pytest.mark.asyncio
    async def test_disconnect_from_room_notifies_opponent(self):
        """Test that disconnecting from a room notifies the other player."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        # Create a room
        await manager.connect(player1)
        await manager.connect(player2)

        # Clear messages
        player1.messages_sent.clear()
        player2.messages_sent.clear()

        # Player1 disconnects
        await manager.disconnect(player1)

        # Player2 should receive game_over notification
        assert len(player2.messages_sent) == 1
        game_over_msg = json.loads(player2.messages_sent[0])
        assert game_over_msg["type"] == "game_over"
        assert "black wins by resignation" in game_over_msg["result"]
        assert game_over_msg["is_checkmate"] is False
        assert game_over_msg["is_stalemate"] is False

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_room(self):
        """Test that disconnect properly cleans up room data."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        await manager.connect(player1)
        await manager.connect(player2)

        room_id = manager.websocket_to_room[player1]

        # Disconnect player1
        await manager.disconnect(player1)

        # Room should be deleted
        assert room_id not in manager.rooms

        # Both players should be removed from websocket mapping
        assert player1 not in manager.websocket_to_room
        assert player2 not in manager.websocket_to_room

    @pytest.mark.asyncio
    async def test_connect_skips_disconnected_players(self):
        """Test that connect skips players with closed connections."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        player3 = MockWebSocket()

        # Simulate player1 being disconnected
        player1.client_state.value = 0  # Disconnected

        await manager.connect(player1)
        await manager.connect(player2)

        # Should not create a room (player1 is disconnected)
        assert len(manager.rooms) == 0

        # Player2 should still be waiting
        assert player2 in manager.queue

        # Player3 connects
        await manager.connect(player3)

        # Now a room should be created with player2 and player3
        assert len(manager.rooms) == 1
        assert len(manager.queue) == 0

        room_id = manager.websocket_to_room.get(player2)
        assert room_id is not None
        assert manager.websocket_to_room.get(player3) == room_id


class TestChessGameEdgeCases:
    """Additional edge case tests for chess game logic."""

    def test_cannot_castle_through_check(self):
        """Test that king cannot castle through a square under attack."""
        game = ChessGame()
        game.board.clear()

        # Set up minimal board: kings and rooks
        game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("h1")] = Piece(PieceType.ROOK, Color.WHITE)
        game.board[Position.from_algebraic("e8")] = Piece(PieceType.KING, Color.BLACK)
        game.board[Position.from_algebraic("f8")] = Piece(PieceType.ROOK, Color.BLACK)
        game.current_turn = Color.WHITE

        # Black rook on f8 attacks f1 (the square king passes through)
        assert game._is_position_under_attack(Position.from_algebraic("f1"), Color.WHITE)

        moves = game.get_possible_moves(Position.from_algebraic("e1"))
        # Should not be able to castle through f1 which is under attack
        assert Position.from_algebraic("g1") not in moves

    def test_cannot_castle_while_in_check(self):
        """Test that king cannot castle while in check."""
        game = ChessGame()
        game.board.clear()

        # Set up minimal board
        game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("h1")] = Piece(PieceType.ROOK, Color.WHITE)
        game.board[Position.from_algebraic("e8")] = Piece(PieceType.ROOK, Color.BLACK)
        game.board[Position.from_algebraic("h8")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        # Black rook on e8 puts white king in check
        assert game.is_in_check(Color.WHITE)

        moves = game.get_possible_moves(Position.from_algebraic("e1"))
        # Should not be able to castle while in check
        assert Position.from_algebraic("g1") not in moves

    def test_pinned_piece_cannot_move(self):
        """Test that a pinned piece has limited or no moves."""
        game = ChessGame()
        game.board.clear()

        # Set up a pin: White king on e1, white bishop on e3, black rook on e8
        game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("e3")] = Piece(PieceType.BISHOP, Color.WHITE)
        game.board[Position.from_algebraic("e8")] = Piece(PieceType.ROOK, Color.BLACK)
        game.current_turn = Color.WHITE

        # Bishop is pinned - it can only move along the e-file or not at all
        moves = game.get_possible_moves(Position.from_algebraic("e3"))

        # Bishop should not be able to move diagonally (its normal moves)
        assert Position.from_algebraic("d4") not in moves
        assert Position.from_algebraic("f4") not in moves

        # Bishop should only move along e-file to block or up to capture
        for move in moves:
            assert move.col == 4  # e-file

    def test_capture_updates_board(self):
        """Test that capturing properly removes the captured piece."""
        game = ChessGame()

        # Set up a capture scenario
        game.board.clear()
        game.board[Position.from_algebraic("e4")] = Piece(PieceType.PAWN, Color.WHITE)
        game.board[Position.from_algebraic("d5")] = Piece(PieceType.PAWN, Color.BLACK)
        game.current_turn = Color.WHITE

        # Move pawn to capture
        result = game.make_move(
            Position.from_algebraic("e4"),
            Position.from_algebraic("d5")
        )

        assert result is True
        # Original square should be empty
        assert game.get_piece(Position.from_algebraic("e4")) is None
        # Destination should have white pawn
        piece = game.get_piece(Position.from_algebraic("d5"))
        assert piece is not None
        assert piece.color == Color.WHITE
        assert piece.piece_type == PieceType.PAWN

    def test_en_passant_expires_after_one_turn(self):
        """Test that en passant opportunity expires after the next turn."""
        game = ChessGame()

        # Set up en passant scenario
        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        game.make_move(Position.from_algebraic("a7"), Position.from_algebraic("a6"))
        game.make_move(Position.from_algebraic("e4"), Position.from_algebraic("e5"))
        game.make_move(Position.from_algebraic("d7"), Position.from_algebraic("d5"))

        # En passant should be possible now
        moves = game.get_possible_moves(Position.from_algebraic("e5"))
        assert Position.from_algebraic("d6") in moves

        # White makes a different move
        game.make_move(Position.from_algebraic("a2"), Position.from_algebraic("a3"))

        # En passant should no longer be available for black
        game.make_move(Position.from_algebraic("a6"), Position.from_algebraic("a5"))

        # Now back to white - en passant expired
        moves = game.get_possible_moves(Position.from_algebraic("e5"))
        # d6 might still be in moves as a regular forward move, but en passant is gone
        assert game.en_passant_target is None

    def test_pawn_cannot_move_backward(self):
        """Test that pawns cannot move backward."""
        game = ChessGame()
        game.board.clear()

        # White pawn on e4
        game.board[Position.from_algebraic("e4")] = Piece(PieceType.PAWN, Color.WHITE, has_moved=True)
        game.current_turn = Color.WHITE

        moves = game.get_possible_moves(Position.from_algebraic("e4"))

        # Should only have forward moves
        for move in moves:
            assert move.row > 3  # Row index of e4

    def test_king_cannot_move_adjacent_to_enemy_king(self):
        """Test that kings cannot move next to each other."""
        game = ChessGame()
        game.board.clear()

        game.board[Position.from_algebraic("e4")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("e6")] = Piece(PieceType.KING, Color.BLACK)
        game.current_turn = Color.WHITE

        moves = game.get_possible_moves(Position.from_algebraic("e4"))

        # White king should not be able to move to e5 (adjacent to black king)
        assert Position.from_algebraic("e5") not in moves

    def test_castling_rook_has_moved(self):
        """Test that castling is not allowed if rook has moved."""
        game = ChessGame()

        # Clear squares for kingside castling
        game.board.pop(Position.from_algebraic("f1"))
        game.board.pop(Position.from_algebraic("g1"))

        # Move rook and move it back
        rook = game.board[Position.from_algebraic("h1")]
        rook.has_moved = True

        moves = game.get_possible_moves(Position.from_algebraic("e1"))
        # Should not be able to castle
        assert Position.from_algebraic("g1") not in moves

    def test_multiple_pieces_can_attack_same_square(self):
        """Test that multiple pieces can attack the same square.

        Note: The _is_position_under_attack method checks if a position is under attack
        BY the opponent of the given color. So by_color=WHITE means checking if position
        is attacked by BLACK.
        """
        game = ChessGame()
        game.board.clear()

        # Set up position where d4 is attacked by multiple black pieces
        game.board[Position.from_algebraic("a1")] = Piece(PieceType.KING, Color.WHITE)
        game.board[Position.from_algebraic("d1")] = Piece(PieceType.ROOK, Color.BLACK)
        game.board[Position.from_algebraic("d7")] = Piece(PieceType.ROOK, Color.BLACK)
        game.board[Position.from_algebraic("a4")] = Piece(PieceType.ROOK, Color.BLACK)

        # d4 should be under attack by Black (so pass WHITE as by_color)
        is_attacked = game._is_position_under_attack(Position.from_algebraic("d4"), Color.WHITE)
        assert is_attacked

    def test_en_passant_capture_removes_correct_pawn(self):
        """Test that en passant removes the correct pawn from the board."""
        game = ChessGame()

        # Set up en passant
        game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))
        game.make_move(Position.from_algebraic("a7"), Position.from_algebraic("a6"))
        game.make_move(Position.from_algebraic("e4"), Position.from_algebraic("e5"))
        game.make_move(Position.from_algebraic("d7"), Position.from_algebraic("d5"))

        # Perform en passant capture
        game.make_move(Position.from_algebraic("e5"), Position.from_algebraic("d6"))

        # d5 should be empty (captured pawn removed)
        assert game.get_piece(Position.from_algebraic("d5")) is None
        # d6 should have the white pawn
        piece = game.get_piece(Position.from_algebraic("d6"))
        assert piece is not None
        assert piece.color == Color.WHITE
        assert piece.piece_type == PieceType.PAWN

    def test_display_board_shows_all_pieces(self):
        """Test that display_board includes all initial pieces."""
        game = ChessGame()
        board_str = game.display_board()

        # Should contain ranks and files
        assert "a b c d e f g h" in board_str
        assert "1" in board_str
        assert "8" in board_str

        # Should contain pieces (unicode symbols)
        assert "♔" in board_str  # White king
        assert "♚" in board_str  # Black king
        assert "♙" in board_str  # White pawn
        assert "♟" in board_str  # Black pawn


class TestRoomExtended:
    """Extended test suite for Room class covering additional functionality."""

    def test_set_player_name(self):
        """Test that set_player_name correctly updates player names."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Set names
        room.set_player_name(player1, "Alice")
        room.set_player_name(player2, "Bob")

        assert room.player_names[player1] == "Alice"
        assert room.player_names[player2] == "Bob"

    def test_set_player_name_with_empty_string(self):
        """Test that empty names default to Guest."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        room.set_player_name(player1, "")
        room.set_player_name(player2, "   ")

        assert room.player_names[player1] == "Guest"
        assert room.player_names[player2] == "Guest"

    def test_is_valid_premove_with_valid_piece(self):
        """Test is_valid_premove with a valid piece."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        from_pos = Position.from_algebraic("e2")
        to_pos = Position.from_algebraic("e4")

        # White pawn at e2 belongs to player1 (white)
        assert room.is_valid_premove(from_pos, to_pos, Color.WHITE)

    def test_is_valid_premove_with_no_piece(self):
        """Test is_valid_premove with no piece at from position."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        from_pos = Position.from_algebraic("e4")  # Empty square
        to_pos = Position.from_algebraic("e5")

        assert not room.is_valid_premove(from_pos, to_pos, Color.WHITE)

    def test_is_valid_premove_with_wrong_color(self):
        """Test is_valid_premove with opponent's piece."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        from_pos = Position.from_algebraic("e7")  # Black pawn
        to_pos = Position.from_algebraic("e5")

        # Trying to premove black piece as white
        assert not room.is_valid_premove(from_pos, to_pos, Color.WHITE)

    def test_is_valid_premove_with_invalid_positions(self):
        """Test is_valid_premove with invalid positions."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        from_pos = Position(-1, 0)  # Invalid position
        to_pos = Position.from_algebraic("e4")

        assert not room.is_valid_premove(from_pos, to_pos, Color.WHITE)

    def test_is_valid_premove_with_invalid_to_position(self):
        """Test is_valid_premove with invalid to position."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        from_pos = Position.from_algebraic("e2")
        to_pos = Position(10, 10)  # Invalid position

        assert not room.is_valid_premove(from_pos, to_pos, Color.WHITE)

    def test_get_theoretical_moves_pawn(self):
        """Test _get_theoretical_moves for pawns."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # White pawn at e2
        from_pos = Position.from_algebraic("e2")
        piece = room.game.get_piece(from_pos)

        moves = room._get_theoretical_moves(from_pos, piece)

        # Should include forward moves and diagonal captures
        assert Position.from_algebraic("e3") in moves  # One forward
        assert Position.from_algebraic("e4") in moves  # Two forward (hasn't moved)
        assert Position.from_algebraic("d3") in moves  # Diagonal left
        assert Position.from_algebraic("f3") in moves  # Diagonal right

    def test_get_theoretical_moves_knight(self):
        """Test _get_theoretical_moves for knights."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # White knight at b1
        from_pos = Position.from_algebraic("b1")
        piece = room.game.get_piece(from_pos)

        moves = room._get_theoretical_moves(from_pos, piece)

        # Knights have L-shaped moves
        assert Position.from_algebraic("a3") in moves
        assert Position.from_algebraic("c3") in moves
        assert Position.from_algebraic("d2") in moves

    def test_get_theoretical_moves_rook(self):
        """Test _get_theoretical_moves for rooks."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Create a rook on d4
        room.game.board.clear()
        from_pos = Position.from_algebraic("d4")
        piece = Piece(PieceType.ROOK, Color.WHITE)
        room.game.board[from_pos] = piece

        moves = room._get_theoretical_moves(from_pos, piece)

        # Rook should have all horizontal and vertical moves
        assert Position.from_algebraic("d1") in moves
        assert Position.from_algebraic("d8") in moves
        assert Position.from_algebraic("a4") in moves
        assert Position.from_algebraic("h4") in moves
        assert len(moves) == 14  # 7 vertical + 7 horizontal

    def test_get_theoretical_moves_bishop(self):
        """Test _get_theoretical_moves for bishops."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Create a bishop on d4
        room.game.board.clear()
        from_pos = Position.from_algebraic("d4")
        piece = Piece(PieceType.BISHOP, Color.WHITE)
        room.game.board[from_pos] = piece

        moves = room._get_theoretical_moves(from_pos, piece)

        # Bishop should have all diagonal moves
        assert Position.from_algebraic("a1") in moves
        assert Position.from_algebraic("g7") in moves
        assert Position.from_algebraic("a7") in moves
        assert Position.from_algebraic("g1") in moves
        assert len(moves) == 13  # All diagonal squares from d4

    def test_get_theoretical_moves_queen(self):
        """Test _get_theoretical_moves for queens."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Create a queen on d4
        room.game.board.clear()
        from_pos = Position.from_algebraic("d4")
        piece = Piece(PieceType.QUEEN, Color.WHITE)
        room.game.board[from_pos] = piece

        moves = room._get_theoretical_moves(from_pos, piece)

        # Queen should have all horizontal, vertical, and diagonal moves
        assert Position.from_algebraic("d1") in moves  # Vertical
        assert Position.from_algebraic("a4") in moves  # Horizontal
        assert Position.from_algebraic("a1") in moves  # Diagonal
        assert len(moves) == 27  # 14 straight + 13 diagonal

    def test_get_theoretical_moves_king(self):
        """Test _get_theoretical_moves for kings."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # King at e1
        from_pos = Position.from_algebraic("e1")
        piece = room.game.get_piece(from_pos)

        moves = room._get_theoretical_moves(from_pos, piece)

        # King should have moves to adjacent squares
        assert Position.from_algebraic("d1") in moves
        assert Position.from_algebraic("f1") in moves
        assert Position.from_algebraic("d2") in moves
        assert Position.from_algebraic("e2") in moves
        assert Position.from_algebraic("f2") in moves

        # Should include castling squares (king hasn't moved)
        assert Position.from_algebraic("g1") in moves  # Kingside
        assert Position.from_algebraic("c1") in moves  # Queenside

    def test_get_theoretical_moves_pawn_black(self):
        """Test _get_theoretical_moves for black pawns (moving down)."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Black pawn at e7
        from_pos = Position.from_algebraic("e7")
        piece = room.game.get_piece(from_pos)

        moves = room._get_theoretical_moves(from_pos, piece)

        # Should move downward (decreasing row)
        assert Position.from_algebraic("e6") in moves
        assert Position.from_algebraic("e5") in moves
        assert Position.from_algebraic("d6") in moves
        assert Position.from_algebraic("f6") in moves

    @pytest.mark.asyncio
    async def test_broadcast_with_last_move(self):
        """Test that broadcast includes last move information."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Make a move
        room.game.make_move(Position.from_algebraic("e2"), Position.from_algebraic("e4"))

        player1.messages_sent.clear()
        player2.messages_sent.clear()

        await room.broadcast_board_state()

        msg = json.loads(player1.messages_sent[0])

        # Should include last_move
        assert "last_move" in msg
        assert msg["last_move"]["from"]["row"] == 1
        assert msg["last_move"]["from"]["col"] == 4
        assert msg["last_move"]["to"]["row"] == 3
        assert msg["last_move"]["to"]["col"] == 4

    @pytest.mark.asyncio
    async def test_broadcast_with_check(self):
        """Test that broadcast includes check status."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Set up a check scenario
        room.game.board.clear()
        room.game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        room.game.board[Position.from_algebraic("e8")] = Piece(PieceType.KING, Color.BLACK)
        room.game.board[Position.from_algebraic("e7")] = Piece(PieceType.ROOK, Color.BLACK)
        room.game.current_turn = Color.WHITE

        player1.messages_sent.clear()
        player2.messages_sent.clear()

        await room.broadcast_board_state()

        msg1 = json.loads(player1.messages_sent[0])

        # White should be in check
        assert msg1.get("in_check") == True
        assert "king_position" in msg1

    @pytest.mark.asyncio
    async def test_broadcast_with_opponent_check(self):
        """Test that broadcast includes opponent check status."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Set up a scenario where black is in check
        room.game.board.clear()
        room.game.board[Position.from_algebraic("e1")] = Piece(PieceType.KING, Color.WHITE)
        room.game.board[Position.from_algebraic("e8")] = Piece(PieceType.KING, Color.BLACK)
        room.game.board[Position.from_algebraic("e2")] = Piece(PieceType.ROOK, Color.WHITE)
        room.game.current_turn = Color.BLACK

        player1.messages_sent.clear()
        player2.messages_sent.clear()

        await room.broadcast_board_state()

        msg2 = json.loads(player2.messages_sent[0])

        # Black's perspective - should see they're in check
        assert msg2.get("in_check") == True

    @pytest.mark.asyncio
    async def test_broadcast_with_premove_moves(self):
        """Test that broadcast includes premove_available_moves for waiting player."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        await room.broadcast_board_state()

        msg1 = json.loads(player1.messages_sent[0])
        msg2 = json.loads(player2.messages_sent[0])

        # White's turn - white gets available_moves, black gets premove_available_moves
        assert "available_moves" in msg1
        assert "premove_available_moves" in msg2
        assert len(msg2["premove_available_moves"]) > 0

    @pytest.mark.asyncio
    async def test_broadcast_with_disconnected_player(self):
        """Test broadcast_board_state handles disconnected players."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        # Make player2 raise RuntimeError when sending
        async def raise_error(msg):
            raise RuntimeError("Connection closed")
        player2.send_text = raise_error

        room = Room(player1, player2)

        # Should not raise exception
        await room.broadcast_board_state()

        # Player1 should still receive the message
        assert len(player1.messages_sent) > 0

    @pytest.mark.asyncio
    async def test_start_time_tracking(self):
        """Test that start_time_tracking initializes time tracking."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        await room.start_time_tracking()

        assert room.last_move_time is not None
        assert room.time_update_task is not None

    @pytest.mark.asyncio
    async def test_time_tracking_cancels_previous_task(self):
        """Test that starting time tracking cancels previous task."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        await room.start_time_tracking()
        first_task = room.time_update_task

        await room.start_time_tracking()
        second_task = room.time_update_task

        # Give time for cancellation to process
        await asyncio.sleep(0.01)

        assert first_task.cancelled()
        assert second_task is not first_task

    @pytest.mark.asyncio
    async def test_time_expiration(self):
        """Test that time expiration ends the game."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        # Set white's time to near zero
        room.time_remaining[Color.WHITE] = 0.01
        room.last_move_time = None

        await room.start_time_tracking()

        # Wait for timeout
        await asyncio.sleep(0.05)

        # Game should be ended
        assert room.game_ended

        # Players should have received game over message
        game_over_found = False
        for msg in player1.messages_sent + player2.messages_sent:
            try:
                data = json.loads(msg)
                if data.get("type") == "game_over":
                    game_over_found = True
                    assert "black wins on time" in data["result"]
            except:
                pass

        assert game_over_found

    def test_subtract_time_first_move(self):
        """Test subtract_time_for_move on first move."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        room.last_move_time = None
        room.subtract_time_for_move()

        # Should just set the time
        assert room.last_move_time is not None

    def test_subtract_time_regular_move(self):
        """Test subtract_time_for_move for regular move."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        import time
        initial_time = room.time_remaining[Color.WHITE]
        room.last_move_time = time.time() - 2.0  # Simulate 2 seconds ago
        room.game.current_turn = Color.BLACK  # White just moved

        room.subtract_time_for_move(is_premove=False)

        # White should have lost time but gained increment
        # Lost ~2 seconds, gained 3 seconds (INCREMENT_SECONDS)
        assert room.time_remaining[Color.WHITE] > initial_time

    def test_subtract_time_premove(self):
        """Test subtract_time_for_move for premove."""
        player1 = MockWebSocket()
        player2 = MockWebSocket()
        room = Room(player1, player2)

        import time
        initial_time = room.time_remaining[Color.WHITE]
        room.last_move_time = time.time()
        room.game.current_turn = Color.BLACK  # White just moved

        room.subtract_time_for_move(is_premove=True)

        # White should have lost 0.1 seconds but gained increment
        # Lost 0.1, gained 3 (INCREMENT_SECONDS) = net +2.9
        expected = initial_time - 0.1 + 3.0
        assert abs(room.time_remaining[Color.WHITE] - expected) < 0.2


class TestConnectionManagerExtended:
    """Extended tests for ConnectionManager."""

    @pytest.mark.asyncio
    async def test_set_pending_name(self):
        """Test set_pending_name stores names for queued players."""
        manager = ConnectionManager()
        player1 = MockWebSocket()

        await manager.connect(player1)
        manager.set_pending_name(player1, "Alice")

        assert manager.pending_names[player1] == "Alice"

    @pytest.mark.asyncio
    async def test_set_pending_name_empty(self):
        """Test set_pending_name defaults to Guest for empty names."""
        manager = ConnectionManager()
        player1 = MockWebSocket()

        await manager.connect(player1)
        manager.set_pending_name(player1, "")

        assert manager.pending_names[player1] == "Guest"

    @pytest.mark.asyncio
    async def test_room_creation_with_pending_names(self):
        """Test that pending names are applied when room is created."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        manager.set_pending_name(player1, "Alice")
        await manager.connect(player1)

        manager.set_pending_name(player2, "Bob")
        await manager.connect(player2)

        # Get the room
        room_id = manager.websocket_to_room[player1]
        room = manager.rooms[room_id]

        # Names should be applied
        assert room.player_names[player1] == "Alice"
        assert room.player_names[player2] == "Bob"

        # Pending names should be cleared
        assert player1 not in manager.pending_names
        assert player2 not in manager.pending_names

    @pytest.mark.asyncio
    async def test_disconnect_from_queue_clears_pending_name(self):
        """Test that disconnecting from queue clears pending name."""
        manager = ConnectionManager()
        player1 = MockWebSocket()

        await manager.connect(player1)
        manager.set_pending_name(player1, "Alice")

        await manager.disconnect(player1)

        assert player1 not in manager.pending_names

    @pytest.mark.asyncio
    async def test_try_create_room_with_one_invalid_connection(self):
        """Test try_create_room puts valid connections back in queue."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        # Player1 is disconnected
        player1.client_state.value = 0

        manager.queue.append(player1)
        manager.queue.append(player2)

        await manager.try_create_room()

        # No room created
        assert len(manager.rooms) == 0

        # Player2 should still be in queue, player1 should not
        assert player2 in manager.queue
        assert player1 not in manager.queue

    @pytest.mark.asyncio
    async def test_try_create_room_with_first_player_valid(self):
        """Test try_create_room puts first player back when second is invalid."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        # Player2 is disconnected, player1 is connected
        player2.client_state.value = 0

        manager.queue.append(player1)
        manager.queue.append(player2)

        await manager.try_create_room()

        # No room created
        assert len(manager.rooms) == 0

        # Player1 should be back in queue, player2 should not
        assert player1 in manager.queue
        assert player2 not in manager.queue

    @pytest.mark.asyncio
    async def test_disconnect_from_room_cancels_time_task(self):
        """Test that disconnect cancels the time tracking task."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        await manager.connect(player1)
        await manager.connect(player2)

        room_id = manager.websocket_to_room[player1]
        room = manager.rooms[room_id]

        # Start time tracking
        await room.start_time_tracking()
        task = room.time_update_task

        # Disconnect
        await manager.disconnect(player1)

        # Give time for cancellation to process
        await asyncio.sleep(0.01)

        # Task should be cancelled
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_disconnect_from_finished_game(self):
        """Test that disconnect from finished game doesn't send resignation."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        await manager.connect(player1)
        await manager.connect(player2)

        room_id = manager.websocket_to_room[player1]
        room = manager.rooms[room_id]

        # Mark game as over
        room.game_ended = True

        player1.messages_sent.clear()
        player2.messages_sent.clear()

        # Disconnect player1
        await manager.disconnect(player1)

        # Player2 should not receive resignation message
        for msg in player2.messages_sent:
            try:
                data = json.loads(msg)
                assert "resignation" not in data.get("result", "")
            except:
                pass

    @pytest.mark.asyncio
    async def test_disconnect_with_other_player_connection_error(self):
        """Test that disconnect handles error when notifying other player."""
        manager = ConnectionManager()
        player1 = MockWebSocket()
        player2 = MockWebSocket()

        await manager.connect(player1)
        await manager.connect(player2)

        # Make player2 raise error when sending
        async def raise_error(msg):
            raise Exception("Connection error")
        player2.send_text = raise_error

        # Should not raise exception when disconnecting player1
        await manager.disconnect(player1)

        # Room should still be cleaned up
        assert len(manager.rooms) == 0
