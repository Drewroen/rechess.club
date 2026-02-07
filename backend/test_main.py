import pytest
import json
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
