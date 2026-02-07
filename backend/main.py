from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional
import uuid
import json
from chess_game import ChessGame, Color, Position, PieceType

app = FastAPI()

class Room:
    def __init__(self, player1: WebSocket, player2: WebSocket) -> None:
        self.id = str(uuid.uuid4())
        self.player1 = player1
        self.player2 = player2
        self.game = ChessGame()

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
                "player_color": color.value
            }

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

class ConnectionManager:
    def __init__(self) -> None:
        self.queue: List[WebSocket] = []
        self.rooms: Dict[str, Room] = {}
        self.websocket_to_room: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.queue.append(websocket)
        await websocket.send_text("Waiting for opponent...")

        # Check if we can create a room
        if len(self.queue) >= 2:
            player1 = self.queue.pop(0)
            player2 = self.queue.pop(0)

            # Validate both connections are still open
            if player1.client_state.value == 1 and player2.client_state.value == 1:
                room = Room(player1, player2)
                self.rooms[room.id] = room
                self.websocket_to_room[player1] = room.id
                self.websocket_to_room[player2] = room.id

                await room.notify_players(f"Match found! Room ID: {room.id}")
                await room.broadcast_board_state()
            else:
                # Put back valid connections to queue
                if player1.client_state.value == 1:
                    self.queue.insert(0, player1)
                if player2.client_state.value == 1:
                    self.queue.insert(0, player2)

    async def disconnect(self, websocket: WebSocket) -> None:
        # Remove from queue if waiting
        if websocket in self.queue:
            self.queue.remove(websocket)
            return

        # Close room if in a room
        if websocket in self.websocket_to_room:
            room_id = self.websocket_to_room[websocket]
            room = self.rooms.get(room_id)

            if room:
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

                # Check if it's the player's turn
                if player_color != room.game.current_turn:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Not your turn"
                    }))
                    continue

                # Parse move positions
                try:
                    from_pos = Position(message["from"]["row"], message["from"]["col"])
                    to_pos = Position(message["to"]["row"], message["to"]["col"])
                    promotion_str = message.get("promotion")  # Optional promotion piece type

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
                except (KeyError, TypeError):
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid move format"
                    }))
                    continue

                # Attempt to make the move
                success = room.game.make_move(from_pos, to_pos, promotion)

                if success:
                    # Broadcast updated board state to both players
                    await room.broadcast_board_state()

                    # Check for game over (checkmate or stalemate)
                    if room.game.is_game_over():
                        game_result = room.game.get_game_result()
                        await room.notify_players(json.dumps({
                            "type": "game_over",
                            "result": game_result,
                            "is_checkmate": room.game.is_checkmate(),
                            "is_stalemate": room.game.is_stalemate()
                        }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid move"
                    }))

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
