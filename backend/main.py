from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional
import uuid
import json
import asyncio
import time
from chess_game import ChessGame, Color, Position, PieceType, Piece

# Time control configuration
STARTING_TIME_SECONDS = 180.0  # Initial time for each player in seconds
INCREMENT_SECONDS = 3.0  # Time added after each move in seconds

app = FastAPI()

class Room:
    def __init__(self, player1: WebSocket, player2: WebSocket) -> None:
        self.id = str(uuid.uuid4())
        self.player1 = player1
        self.player2 = player2
        self.game = ChessGame()
        self.premoves: Dict[WebSocket, Dict] = {}  # Store premoves per player
        self.game_ended = False  # Track if game has ended by any means
        self.player_names: Dict[WebSocket, str] = {player1: "Guest", player2: "Guest"}  # Store player names

        # Time controls: each player starts with configured time
        self.time_remaining: Dict[Color, float] = {
            Color.WHITE: STARTING_TIME_SECONDS,
            Color.BLACK: STARTING_TIME_SECONDS
        }
        self.last_move_time: Optional[float] = None  # Timestamp of last move
        self.time_update_task: Optional[asyncio.Task] = None  # Background task for time updates

    async def notify_players(self, message: str) -> None:
        try:
            await self.player1.send_text(message)
        except RuntimeError:
            pass  # Player1 connection already closed
        try:
            await self.player2.send_text(message)
        except RuntimeError:
            pass  # Player2 connection already closed

    async def broadcast_board_state(self) -> None:
        """Broadcast the current board state to all players as a structured JSON object."""
        # Send personalized board state to each player with their color
        for player, color in [(self.player1, Color.WHITE), (self.player2, Color.BLACK)]:
            # Create a snapshot of the board to avoid dictionary modification during iteration
            board_snapshot = list(self.game.board.items())

            # Get opponent websocket
            opponent = self.player2 if player == self.player1 else self.player1

            board_state = {
                "type": "board_state",
                "board": {
                    f"{pos.row},{pos.col}": {
                        "piece_type": piece.piece_type.value if hasattr(piece.piece_type, 'value') else piece.piece_type,
                        "color": piece.color.value
                    }
                    for pos, piece in board_snapshot
                },
                "current_turn": self.game.current_turn.value,
                "room_id": self.id,
                "player_color": color.value,
                "opponent_name": self.player_names[opponent],
                "white_time": round(self.time_remaining[Color.WHITE], 1),
                "black_time": round(self.time_remaining[Color.BLACK], 1),
                "captured_pieces": {
                    "white": [
                        {
                            "piece_type": piece.piece_type.value if hasattr(piece.piece_type, 'value') else piece.piece_type,
                            "color": piece.color.value
                        }
                        for piece in self.game.captured_pieces[Color.WHITE]
                    ],
                    "black": [
                        {
                            "piece_type": piece.piece_type.value if hasattr(piece.piece_type, 'value') else piece.piece_type,
                            "color": piece.color.value
                        }
                        for piece in self.game.captured_pieces[Color.BLACK]
                    ]
                }
            }

            # Add last move information if there is a move history
            if self.game.move_history:
                last_move = self.game.move_history[-1]
                board_state["last_move"] = {
                    "from": {"row": last_move.from_pos.row, "col": last_move.from_pos.col},
                    "to": {"row": last_move.to_pos.row, "col": last_move.to_pos.col}
                }

            # Add check status and king position for both players
            # Check if this player's king is in check
            if self.game.is_in_check(color):
                for pos, piece in board_snapshot:
                    if piece.piece_type == PieceType.KING and piece.color == color:
                        board_state["in_check"] = True
                        board_state["king_position"] = {"row": pos.row, "col": pos.col}
                        break

            # Check if opponent's king is in check
            opponent_color = Color.BLACK if color == Color.WHITE else Color.WHITE
            if self.game.is_in_check(opponent_color):
                for pos, piece in board_snapshot:
                    if piece.piece_type == PieceType.KING and piece.color == opponent_color:
                        board_state["opponent_in_check"] = True
                        board_state["opponent_king_position"] = {"row": pos.row, "col": pos.col}
                        break

            # Add available moves for the player whose turn it is
            if color == self.game.current_turn:
                available_moves = {}
                for pos, piece in board_snapshot:
                    if piece.color == color:
                        moves = self.game.get_possible_moves(pos)
                        if moves:
                            available_moves[f"{pos.row},{pos.col}"] = [
                                {"row": move.row, "col": move.col} for move in moves
                            ]
                board_state["available_moves"] = available_moves
            else:
                # Add available premove moves for the player waiting for their turn
                premove_moves = {}
                for pos, piece in board_snapshot:
                    if piece.color == color:
                        # For premoves, show all theoretically possible moves for the piece
                        # This will be validated when the premove is actually attempted
                        moves = self._get_theoretical_moves(pos, piece)
                        if moves:
                            premove_moves[f"{pos.row},{pos.col}"] = [
                                {"row": move.row, "col": move.col} for move in moves
                            ]
                board_state["premove_available_moves"] = premove_moves

            message = json.dumps(board_state)
            try:
                await player.send_text(message)
            except RuntimeError:
                pass  # Player connection already closed

    def has_player(self, websocket: WebSocket) -> bool:
        return websocket == self.player1 or websocket == self.player2

    def get_player_color(self, websocket: WebSocket) -> Optional[Color]:
        """Get the color assigned to a player's websocket."""
        if websocket == self.player1:
            return Color.WHITE
        elif websocket == self.player2:
            return Color.BLACK
        return None

    def set_player_name(self, websocket: WebSocket, name: str) -> None:
        """Set the name for a player."""
        if websocket in self.player_names:
            self.player_names[websocket] = name if name.strip() else "Guest"

    def _get_theoretical_moves(self, from_pos: Position, piece: Piece) -> List[Position]:
        """Get all theoretical moves for a piece (for premove suggestions).

        This returns all squares a piece could potentially move to, regardless of
        the current board state. This allows premoves to capture pieces that will
        move into position, or move to squares that will become available.
        """
        moves = []

        if piece.piece_type == PieceType.PAWN:
            # Pawns can move forward 1 or 2 squares (if not moved) and capture diagonally
            direction = 1 if piece.color == Color.WHITE else -1

            # Forward moves (1 square)
            forward_pos = from_pos.offset(direction, 0)
            if forward_pos.is_valid():
                moves.append(forward_pos)

            # Double move (2 squares) - only from starting position
            if not piece.has_moved:
                double_forward = from_pos.offset(2 * direction, 0)
                if double_forward.is_valid():
                    moves.append(double_forward)

            # Diagonal captures (both directions)
            for col_offset in [-1, 1]:
                capture_pos = from_pos.offset(direction, col_offset)
                if capture_pos.is_valid():
                    moves.append(capture_pos)

        elif piece.piece_type == PieceType.KNIGHT:
            # Knights can jump to 8 possible squares
            knight_offsets = [
                (2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)
            ]
            for row_offset, col_offset in knight_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.KING:
            # Kings can move one square in any direction
            for row_offset in [-1, 0, 1]:
                for col_offset in [-1, 0, 1]:
                    if row_offset == 0 and col_offset == 0:
                        continue
                    to_pos = from_pos.offset(row_offset, col_offset)
                    if to_pos.is_valid():
                        moves.append(to_pos)

            # Castling squares (if king hasn't moved)
            if not piece.has_moved:
                # Kingside castling
                kingside_pos = from_pos.offset(0, 2)
                if kingside_pos.is_valid():
                    moves.append(kingside_pos)
                # Queenside castling
                queenside_pos = from_pos.offset(0, -2)
                if queenside_pos.is_valid():
                    moves.append(queenside_pos)

        elif piece.piece_type == PieceType.MANN:
            # Mann moves one square in any direction (like king but non-royal)
            for row_offset in [-1, 0, 1]:
                for col_offset in [-1, 0, 1]:
                    if row_offset == 0 and col_offset == 0:
                        continue
                    to_pos = from_pos.offset(row_offset, col_offset)
                    if to_pos.is_valid():
                        moves.append(to_pos)

        elif piece.piece_type in [PieceType.ROOK, PieceType.BISHOP, PieceType.QUEEN]:
            # Sliding pieces - show all squares in their movement directions
            if piece.piece_type == PieceType.ROOK:
                directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            elif piece.piece_type == PieceType.BISHOP:
                directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            else:  # QUEEN
                directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]

            for row_delta, col_delta in directions:
                current_pos = from_pos
                # Continue sliding until we hit the board edge
                while True:
                    current_pos = current_pos.offset(row_delta, col_delta)
                    if not current_pos.is_valid():
                        break
                    moves.append(current_pos)

        elif piece.piece_type == PieceType.ELEPHANT:
            # Elephant moves diagonally up to 2 squares
            directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            for row_delta, col_delta in directions:
                for distance in range(1, 3):  # Max 2 squares
                    to_pos = from_pos.offset(row_delta * distance, col_delta * distance)
                    if to_pos.is_valid():
                        moves.append(to_pos)

        elif piece.piece_type == PieceType.GIRAFFE:
            # Giraffe moves 4 squares in one direction, 1 in perpendicular
            giraffe_offsets = [
                (4, 1), (4, -1), (-4, 1), (-4, -1),
                (1, 4), (1, -4), (-1, 4), (-1, -4)
            ]
            for row_offset, col_offset in giraffe_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.UNICORN:
            # Unicorn (nightrider) - sliding knight moves
            knight_offsets = [
                (2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)
            ]
            for row_delta, col_delta in knight_offsets:
                current_pos = from_pos
                # Continue sliding in knight-move increments until we hit the board edge
                while True:
                    current_pos = current_pos.offset(row_delta, col_delta)
                    if not current_pos.is_valid():
                        break
                    moves.append(current_pos)

        elif piece.piece_type == PieceType.CENTAUR:
            # Centaur combines knight and king movements
            # Knight moves
            knight_offsets = [
                (2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)
            ]
            for row_offset, col_offset in knight_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

            # King moves (one square in any direction)
            for row_offset in [-1, 0, 1]:
                for col_offset in [-1, 0, 1]:
                    if row_offset == 0 and col_offset == 0:
                        continue
                    to_pos = from_pos.offset(row_offset, col_offset)
                    if to_pos.is_valid():
                        moves.append(to_pos)

        elif piece.piece_type == PieceType.CHAMPION:
            # Champion: jumps 2 squares orthogonally/diagonally or slides 1 square orthogonally
            # Jump two squares orthogonally
            orthogonal_jumps = [
                (2, 0), (-2, 0), (0, 2), (0, -2)
            ]
            for row_offset, col_offset in orthogonal_jumps:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

            # Jump two squares diagonally
            diagonal_jumps = [
                (2, 2), (2, -2), (-2, 2), (-2, -2)
            ]
            for row_offset, col_offset in diagonal_jumps:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

            # Slide one square orthogonally (non-jumping)
            orthogonal_slides = [
                (1, 0), (-1, 0), (0, 1), (0, -1)
            ]
            for row_offset, col_offset in orthogonal_slides:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.WIZARD:
            # Wizard: jumps (1,3) or (3,1) or slides 1 square diagonally
            # Jump (1,3) or (3,1) squares
            wizard_jumps = [
                (1, 3), (1, -3), (-1, 3), (-1, -3),
                (3, 1), (3, -1), (-3, 1), (-3, -1)
            ]
            for row_offset, col_offset in wizard_jumps:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

            # Slide one square diagonally (non-jumping)
            diagonal_slides = [
                (1, 1), (1, -1), (-1, 1), (-1, -1)
            ]
            for row_offset, col_offset in diagonal_slides:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.AMAZON:
            # Amazon combines queen and knight movements
            # Queen moves (sliding in all 8 directions)
            queen_directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
            for row_delta, col_delta in queen_directions:
                current_pos = from_pos
                # Continue sliding until we hit the board edge
                while True:
                    current_pos = current_pos.offset(row_delta, col_delta)
                    if not current_pos.is_valid():
                        break
                    moves.append(current_pos)

            # Knight moves
            knight_offsets = [
                (2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)
            ]
            for row_offset, col_offset in knight_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.DRAGON:
            # Dragon combines knight and pawn movements
            direction = 1 if piece.color == Color.WHITE else -1

            # Knight moves
            knight_offsets = [
                (2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)
            ]
            for row_offset, col_offset in knight_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

            # Forward move (1 square)
            forward_pos = from_pos.offset(direction, 0)
            if forward_pos.is_valid():
                moves.append(forward_pos)

            # Diagonal captures
            for col_offset in [-1, 1]:
                capture_pos = from_pos.offset(direction, col_offset)
                if capture_pos.is_valid():
                    moves.append(capture_pos)

        elif piece.piece_type == PieceType.ZEBRA:
            # Zebra moves (2,3)-leaper
            zebra_offsets = [
                (2, 3), (2, -3), (-2, 3), (-2, -3),
                (3, 2), (3, -2), (-3, 2), (-3, -2)
            ]
            for row_offset, col_offset in zebra_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.CHANCELLOR:
            # Chancellor combines rook and knight movements
            # Rook moves (sliding orthogonally)
            rook_directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            for row_delta, col_delta in rook_directions:
                current_pos = from_pos
                # Continue sliding until we hit the board edge
                while True:
                    current_pos = current_pos.offset(row_delta, col_delta)
                    if not current_pos.is_valid():
                        break
                    moves.append(current_pos)

            # Knight moves
            knight_offsets = [
                (2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)
            ]
            for row_offset, col_offset in knight_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.ARCHBISHOP:
            # Archbishop combines bishop and knight movements
            # Bishop moves (sliding diagonally)
            bishop_directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            for row_delta, col_delta in bishop_directions:
                current_pos = from_pos
                # Continue sliding until we hit the board edge
                while True:
                    current_pos = current_pos.offset(row_delta, col_delta)
                    if not current_pos.is_valid():
                        break
                    moves.append(current_pos)

            # Knight moves
            knight_offsets = [
                (2, 1), (2, -1), (-2, 1), (-2, -1),
                (1, 2), (1, -2), (-1, 2), (-1, -2)
            ]
            for row_offset, col_offset in knight_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        elif piece.piece_type == PieceType.SHIP:
            # Ship moves (2,2)-leaper - diagonal jumps of 2 squares
            ship_offsets = [
                (2, 2), (2, -2), (-2, 2), (-2, -2)
            ]
            for row_offset, col_offset in ship_offsets:
                to_pos = from_pos.offset(row_offset, col_offset)
                if to_pos.is_valid():
                    moves.append(to_pos)

        return moves

    def is_valid_premove(self, from_pos: Position, to_pos: Position, player_color: Color) -> bool:
        """Check if a move could possibly be valid for the player when it becomes their turn."""
        # Check if there's a piece at the from position
        piece = self.game.get_piece(from_pos)
        if not piece:
            return False

        # Check if the piece belongs to the player
        if piece.color != player_color:
            return False

        # Check if positions are valid
        if not from_pos.is_valid() or not to_pos.is_valid():
            return False

        # For premoves, we allow any move that could theoretically be valid
        # We don't check if it's currently legal, just if it's a possible move for that piece type
        return True

    async def start_time_tracking(self) -> None:
        """Start tracking time for the current player's turn."""
        self.last_move_time = time.time()

        # Cancel previous timeout if exists
        if self.time_update_task:
            self.time_update_task.cancel()

        # Schedule timeout for when current player's time expires
        current_color = self.game.current_turn
        time_remaining = self.time_remaining[current_color]

        self.time_update_task = asyncio.create_task(
            self._sleep_until_timeout(time_remaining, current_color)
        )

    async def _sleep_until_timeout(self, duration: float, color: Color) -> None:
        """Sleep until the player's time expires, then end the game."""
        try:
            await asyncio.sleep(duration)

            # Time expired
            self.time_remaining[color] = 0
            await self._handle_time_expiration(color)

        except asyncio.CancelledError:
            # Player made a move before timeout - that's expected
            pass


    async def _handle_time_expiration(self, color: Color) -> None:
        """Handle when a player runs out of time."""
        self.game_ended = True
        winner_color = color.opposite()
        await self.notify_players(json.dumps({
            "type": "game_over",
            "result": f"{winner_color.value} wins on time",
            "is_checkmate": False,
            "is_stalemate": False
        }))

    def subtract_time_for_move(self, is_premove: bool = False) -> None:
        """Subtract time from the player who just moved and add increment."""
        if self.last_move_time is None:
            # First move of the game, just set the time
            self.last_move_time = time.time()
            return

        # Calculate elapsed time since last move
        current_time = time.time()
        elapsed = current_time - self.last_move_time

        # Get the player who just moved (opposite of current turn since turn already switched)
        player_who_moved = self.game.current_turn.opposite()

        if is_premove:
            # Premove: subtract 0.1 seconds
            self.time_remaining[player_who_moved] = max(0, round(self.time_remaining[player_who_moved] - 0.1, 1))
        else:
            # Regular move: subtract elapsed time
            self.time_remaining[player_who_moved] = max(0, round(self.time_remaining[player_who_moved] - elapsed, 1))

        # Add increment after every move
        self.time_remaining[player_who_moved] = round(self.time_remaining[player_who_moved] + INCREMENT_SECONDS, 1)

        # Reset last move time to now for the next player
        self.last_move_time = current_time

class ConnectionManager:
    def __init__(self) -> None:
        self.queue: List[WebSocket] = []
        self.rooms: Dict[str, Room] = {}
        self.websocket_to_room: Dict[WebSocket, str] = {}
        self.pending_names: Dict[WebSocket, str] = {}  # Store names before room is created

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.queue.append(websocket)
        await websocket.send_text("Waiting for opponent...")
        await self.try_create_room()

    async def try_create_room(self) -> None:
        """Try to create a room if there are at least 2 players in queue."""
        # Check if we can create a room
        if len(self.queue) >= 2:
            player1 = self.queue.pop(0)
            player2 = self.queue.pop(0)

            # Validate both connections are still open
            if player1.client_state.value == 1 and player2.client_state.value == 1:
                room = Room(player1, player2)

                # Set player names if they were provided
                if player1 in self.pending_names:
                    room.set_player_name(player1, self.pending_names[player1])
                    del self.pending_names[player1]
                if player2 in self.pending_names:
                    room.set_player_name(player2, self.pending_names[player2])
                    del self.pending_names[player2]

                self.rooms[room.id] = room
                self.websocket_to_room[player1] = room.id
                self.websocket_to_room[player2] = room.id

                await room.notify_players(f"Match found! Room ID: {room.id}")
                await room.broadcast_board_state()
                # Start time tracking for the game
                await room.start_time_tracking()
            else:
                # Put back valid connections to queue
                if player1.client_state.value == 1:
                    self.queue.insert(0, player1)
                if player2.client_state.value == 1:
                    self.queue.insert(0, player2)

    def set_pending_name(self, websocket: WebSocket, name: str) -> None:
        """Store a player's name while they're in the queue."""
        self.pending_names[websocket] = name if name.strip() else "Guest"

    async def disconnect(self, websocket: WebSocket) -> None:
        # Remove from queue if waiting
        if websocket in self.queue:
            self.queue.remove(websocket)
            # Clean up pending name
            if websocket in self.pending_names:
                del self.pending_names[websocket]
            return

        # Close room if in a room
        if websocket in self.websocket_to_room:
            room_id = self.websocket_to_room[websocket]
            room = self.rooms.get(room_id)

            if room:
                # Cancel time tracking task
                if room.time_update_task:
                    room.time_update_task.cancel()

                # Only send resignation message if the game wasn't already over
                if not room.game.is_game_over() and not room.game_ended:
                    room.game_ended = True
                    # Determine winner (the player who stayed connected)
                    other_player = room.player2 if websocket == room.player1 else room.player1
                    winner_color = room.get_player_color(other_player)

                    # Notify other player of win by resignation (don't close their connection)
                    try:
                        await other_player.send_text(json.dumps({
                            "type": "game_over",
                            "result": f"{winner_color.value} wins by resignation",
                            "is_checkmate": False,
                            "is_stalemate": False
                        }))
                    except:
                        pass

                # Clean up
                del self.websocket_to_room[room.player1]
                del self.websocket_to_room[room.player2]
                del self.rooms[room_id]

manager = ConnectionManager()

@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()

            # Parse incoming message
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue

            # Handle name setting
            if message.get("type") == "set_name":
                name = message.get("name", "Guest")

                # Check if player is already in a room
                room_id = manager.websocket_to_room.get(websocket)
                if room_id:
                    room = manager.rooms.get(room_id)
                    if room:
                        room.set_player_name(websocket, name)
                        # Re-broadcast board state with updated name
                        await room.broadcast_board_state()
                else:
                    # Player is in queue, store name for later
                    manager.set_pending_name(websocket, name)
                    # Try to create a room now that name is set
                    await manager.try_create_room()
                continue

            # Handle cancel premove requests
            if message.get("type") == "cancel_premove":
                room_id = manager.websocket_to_room.get(websocket)
                if not room_id:
                    continue

                room = manager.rooms.get(room_id)
                if not room:
                    continue

                # Clear the premove for this player if one exists
                if websocket in room.premoves:
                    del room.premoves[websocket]
                    await websocket.send_text(json.dumps({
                        "type": "premove_cancelled"
                    }))
                continue

            # Handle move requests
            if message.get("type") == "move":
                room_id = manager.websocket_to_room.get(websocket)
                if not room_id:
                    continue

                room = manager.rooms.get(room_id)
                if not room:
                    continue

                # Get player color
                player_color = room.get_player_color(websocket)
                if not player_color:
                    continue

                # Parse move positions first to use in premove validation
                try:
                    from_pos = Position(message["from"]["row"], message["from"]["col"])
                    to_pos = Position(message["to"]["row"], message["to"]["col"])
                    promotion_str = message.get("promotion")  # Optional promotion piece type
                except (KeyError, TypeError):
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid move format"
                    }))
                    continue

                # Check if it's the player's turn
                if player_color != room.game.current_turn:
                    # Not the player's turn - treat as a premove
                    if room.is_valid_premove(from_pos, to_pos, player_color):
                        # Store the premove (replaces any existing premove)
                        room.premoves[websocket] = {
                            "from": message["from"],
                            "to": message["to"],
                            "promotion": promotion_str
                        }
                        await websocket.send_text(json.dumps({
                            "type": "premove_set",
                            "from": message["from"],
                            "to": message["to"]
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Invalid premove"
                        }))
                    continue

                # Convert string promotion type to PieceType enum
                promotion = None
                if promotion_str:
                    try:
                        promotion = PieceType(promotion_str)
                    except ValueError:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Invalid promotion type: {promotion_str}"
                        }))
                        continue

                # Attempt to make the move
                success = room.game.make_move(from_pos, to_pos, promotion)

                if success:
                    # Subtract time for regular move
                    room.subtract_time_for_move(is_premove=False)

                    # Clear the premove for the player who just moved
                    if websocket in room.premoves:
                        del room.premoves[websocket]

                    # Broadcast updated board state to both players
                    await room.broadcast_board_state()

                    # Check for game over (checkmate or stalemate)
                    if room.game.is_game_over():
                        # Cancel time tracking task
                        if room.time_update_task:
                            room.time_update_task.cancel()

                        room.game_ended = True
                        game_result = room.game.get_game_result()
                        await room.notify_players(json.dumps({
                            "type": "game_over",
                            "result": game_result,
                            "is_checkmate": room.game.is_checkmate(),
                            "is_stalemate": room.game.is_stalemate()
                        }))
                    else:
                        # Restart time tracking for the next player
                        await room.start_time_tracking()
                        # Check if the opponent has a premove
                        opponent = room.player2 if websocket == room.player1 else room.player1
                        if opponent in room.premoves:
                            premove_data = room.premoves[opponent]

                            # Try to execute the premove
                            try:
                                premove_from = Position(premove_data["from"]["row"], premove_data["from"]["col"])
                                premove_to = Position(premove_data["to"]["row"], premove_data["to"]["col"])
                                premove_promotion_str = premove_data.get("promotion")

                                # Convert promotion string to PieceType if present
                                premove_promotion = None
                                if premove_promotion_str:
                                    try:
                                        premove_promotion = PieceType(premove_promotion_str)
                                    except ValueError:
                                        pass

                                # Attempt the premove
                                premove_success = room.game.make_move(premove_from, premove_to, premove_promotion)

                                # Clear the premove regardless of success
                                del room.premoves[opponent]

                                if premove_success:
                                    # Subtract time for premove (0.1 seconds)
                                    room.subtract_time_for_move(is_premove=True)

                                    # Broadcast the new board state
                                    await room.broadcast_board_state()

                                    # Check for game over after premove
                                    if room.game.is_game_over():
                                        # Cancel time tracking task
                                        if room.time_update_task:
                                            room.time_update_task.cancel()

                                        room.game_ended = True
                                        game_result = room.game.get_game_result()
                                        await room.notify_players(json.dumps({
                                            "type": "game_over",
                                            "result": game_result,
                                            "is_checkmate": room.game.is_checkmate(),
                                            "is_stalemate": room.game.is_stalemate()
                                        }))
                                    else:
                                        # Restart time tracking for the next player
                                        await room.start_time_tracking()
                            except (KeyError, TypeError):
                                # Invalid premove data, just clear it
                                if opponent in room.premoves:
                                    del room.premoves[opponent]
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid move"
                    }))

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
