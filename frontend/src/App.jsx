import { useState, useEffect, useRef } from 'react'
import './App.css'
import { getPieceSvgPath } from './services/chessPieces'

// Helper function to format time (seconds) as MM:SS.t
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const tenths = Math.floor((seconds % 1) * 10)
  return `${mins}:${secs.toString().padStart(2, '0')}.${tenths}`
}

// Helper function to render board with checkered pattern
function renderBoard(boardState, selectedSquare, onSquareClick, isGameOver = false, draggedPiece = null, onPieceMouseDown = null, premove = null) {
  if (!boardState || !boardState.board) return null

  const board = boardState.board
  const squareSize = 88 // Size of each square in pixels
  const isBlack = boardState.player_color === 'black'

  // Determine if it's the player's turn
  const isPlayerTurn = boardState.current_turn === boardState.player_color

  // Get available moves for the selected piece
  // Use regular moves if it's player's turn, premoves if not
  const availableMoves = selectedSquare
    ? (isPlayerTurn
        ? (boardState.available_moves?.[`${selectedSquare.row},${selectedSquare.col}`] || [])
        : (boardState.premove_available_moves?.[`${selectedSquare.row},${selectedSquare.col}`] || []))
    : []

  // Get last move information
  const lastMove = boardState.last_move || null

  return (
    <svg
      width={squareSize * 8}
      height={squareSize * 8}
      viewBox={`0 0 ${squareSize * 8} ${squareSize * 8}`}
      style={{
        border: 'none',
        filter: isGameOver ? 'grayscale(100%)' : 'none',
        maxWidth: '704px',
        maxHeight: 'min(704px, calc(100vh - 12rem))',
        width: '100%',
        height: 'auto',
        display: 'block'
      }}
    >
      {/* Render checkered board pattern */}
      {Array.from({ length: 8 }).map((_, row) =>
        Array.from({ length: 8 }).map((_, col) => {
          // Convert SVG row to board row
          // If white: row 7 at top (row 0 = SVG row 7)
          // If black: row 0 at top (row 0 = SVG row 0), flip the board
          const boardRow = isBlack ? row : 7 - row
          const boardCol = isBlack ? 7 - col : col

          // Calculate if square should be light or dark
          const isLightSquare = (row + col) % 2 === 0
          const fillColor = isLightSquare ? '#e8eaec' : '#798495'

          return (
            <rect
              key={`${row}-${col}`}
              x={col * squareSize}
              y={row * squareSize}
              width={squareSize}
              height={squareSize}
              fill={fillColor}
              style={{ cursor: 'pointer' }}
              onClick={() => onSquareClick(boardRow, boardCol)}
            />
          )
        })
      )}

      {/* Render last move highlight */}
      {lastMove && Array.from({ length: 8 }).map((_, row) =>
        Array.from({ length: 8 }).map((_, col) => {
          const boardRow = isBlack ? row : 7 - row
          const boardCol = isBlack ? 7 - col : col

          // Check if this square is either the from or to position of the last move
          const isLastMoveSquare =
            (lastMove.from.row === boardRow && lastMove.from.col === boardCol) ||
            (lastMove.to.row === boardRow && lastMove.to.col === boardCol)

          if (isLastMoveSquare) {
            return (
              <rect
                key={`lastmove-${row}-${col}`}
                x={col * squareSize}
                y={row * squareSize}
                width={squareSize}
                height={squareSize}
                fill="rgba(155, 199, 0, .41)"
                style={{ pointerEvents: 'none' }}
              />
            )
          }
          return null
        })
      )}

      {/* Render selected square highlight */}
      {selectedSquare && Array.from({ length: 8 }).map((_, row) =>
        Array.from({ length: 8 }).map((_, col) => {
          const boardRow = isBlack ? row : 7 - row
          const boardCol = isBlack ? 7 - col : col

          if (selectedSquare.row === boardRow && selectedSquare.col === boardCol) {
            return (
              <rect
                key={`selected-${row}-${col}`}
                x={col * squareSize}
                y={row * squareSize}
                width={squareSize}
                height={squareSize}
                fill="rgba(20, 85, 30, 0.5)"
                style={{ pointerEvents: 'none' }}
              />
            )
          }
          return null
        })
      )}

      {/* Render available move indicators */}
      {availableMoves.map((move, idx) => {
        // Convert board coordinates to SVG coordinates
        const svgRow = isBlack ? move.row : 7 - move.row
        const svgCol = isBlack ? 7 - move.col : move.col
        const x = svgCol * squareSize
        const y = svgRow * squareSize

        // Check if this move captures a piece
        const pieceKey = `${move.row},${move.col}`
        const isCapture = board[pieceKey] !== undefined

        // Use different colors for premoves vs regular moves
        const isPremoveMode = !isPlayerTurn
        const dotColor = isPremoveMode ? 'rgba(20, 30, 85, .5)' : 'rgba(20, 85, 30, 0.5)'
        const ringColor = isPremoveMode ? 'rgba(20, 30, 85, 0.3)' : 'rgba(20, 85, 0, 0.3)'

        return (
          <foreignObject
            key={`move-${idx}`}
            x={x}
            y={y}
            width={squareSize}
            height={squareSize}
            style={{ pointerEvents: 'none' }}
          >
            <div style={{
              width: '100%',
              height: '100%',
              background: isCapture
                ? `radial-gradient(transparent 0%, transparent 79%, ${ringColor} calc(80% + 1px))`
                : `radial-gradient(${dotColor} 19%, rgba(0, 0, 0, 0) calc(20% + 1px))`
            }} />
          </foreignObject>
        )
      })}

      {/* Render premove overlay (from and to squares) */}
      {premove && Array.from({ length: 8 }).map((_, row) =>
        Array.from({ length: 8 }).map((_, col) => {
          const boardRow = isBlack ? row : 7 - row
          const boardCol = isBlack ? 7 - col : col

          // Check if this square is either the from or to position of the premove
          const isPremoveSquare =
            (premove.from.row === boardRow && premove.from.col === boardCol) ||
            (premove.to.row === boardRow && premove.to.col === boardCol)

          if (isPremoveSquare) {
            return (
              <rect
                key={`premove-${row}-${col}`}
                x={col * squareSize}
                y={row * squareSize}
                width={squareSize}
                height={squareSize}
                fill="rgba(20, 30, 85, .5)"
                style={{ pointerEvents: 'none' }}
              />
            )
          }
          return null
        })
      )}

      {/* Render check overlay on king square */}
      {boardState.in_check && boardState.king_position && (() => {
        const kingPos = boardState.king_position
        const svgRow = isBlack ? kingPos.row : 7 - kingPos.row
        const svgCol = isBlack ? 7 - kingPos.col : kingPos.col
        const x = svgCol * squareSize
        const y = svgRow * squareSize

        return (
          <foreignObject
            key="check-overlay"
            x={x}
            y={y}
            width={squareSize}
            height={squareSize}
            style={{ pointerEvents: 'none' }}
          >
            <div style={{
              width: '100%',
              height: '100%',
              background: 'radial-gradient(ellipse at center, rgb(255, 0, 0) 0%, rgb(231, 0, 0) 25%, rgba(169, 0, 0, 0) 89%, rgba(158, 0, 0, 0) 100%)'
            }} />
          </foreignObject>
        )
      })()}

      {/* Render check overlay on opponent's king square */}
      {boardState.opponent_in_check && boardState.opponent_king_position && (() => {
        const kingPos = boardState.opponent_king_position
        const svgRow = isBlack ? kingPos.row : 7 - kingPos.row
        const svgCol = isBlack ? 7 - kingPos.col : kingPos.col
        const x = svgCol * squareSize
        const y = svgRow * squareSize

        return (
          <foreignObject
            key="opponent-check-overlay"
            x={x}
            y={y}
            width={squareSize}
            height={squareSize}
            style={{ pointerEvents: 'none' }}
          >
            <div style={{
              width: '100%',
              height: '100%',
              background: 'radial-gradient(ellipse at center, rgb(255, 0, 0) 0%, rgb(231, 0, 0) 25%, rgba(169, 0, 0, 0) 89%, rgba(158, 0, 0, 0) 100%)'
            }} />
          </foreignObject>
        )
      })()}

      {/* Render pieces on top of the board */}
      {Object.entries(board).map(([key, piece]) => {
        const [row, col] = key.split(',').map(Number)

        // Skip rendering the piece being dragged
        if (draggedPiece && draggedPiece.row === row && draggedPiece.col === col) {
          return null
        }

        // Convert board coordinates to SVG coordinates
        // If white: row 7 at top (board row 0 = SVG row 7)
        // If black: row 0 at top (board row 0 = SVG row 0), flip the board
        const svgY = isBlack ? row * squareSize : (7 - row) * squareSize
        const svgX = isBlack ? (7 - col) * squareSize : col * squareSize

        return (
          <image
            key={key}
            href={getPieceSvgPath(piece.piece_type, piece.color)}
            x={svgX}
            y={svgY}
            width={squareSize}
            height={squareSize}
            style={{ cursor: 'pointer', pointerEvents: 'all' }}
            onClick={() => onSquareClick(row, col)}
            onMouseDown={(e) => onPieceMouseDown && onPieceMouseDown(e, row, col)}
          />
        )
      })}
    </svg>
  )
}

function App() {
  const [boardState, setBoardState] = useState(null)
  const [selectedSquare, setSelectedSquare] = useState(null) // { row, col } or null
  const [gameState, setGameState] = useState('landing') // 'landing', 'queue', 'playing'
  const [promotionPending, setPromotionPending] = useState(null) // { from, to } or null
  const [gameOver, setGameOver] = useState(null) // { result, is_checkmate, is_stalemate } or null
  const [draggedPiece, setDraggedPiece] = useState(null) // { row, col, piece, clientX, clientY } or null
  const [premove, setPremove] = useState(null) // { from: { row, col }, to: { row, col } } or null
  const [whiteTime, setWhiteTime] = useState(180.0) // Timer state for white
  const [blackTime, setBlackTime] = useState(180.0) // Timer state for black
  const [playerName, setPlayerName] = useState(() => {
    // Load player name from localStorage, default to 'Guest'
    return localStorage.getItem('playerName') || 'Guest'
  }) // Player's name input
  const [opponentName, setOpponentName] = useState('Guest') // Opponent's name
  const [inputWidth, setInputWidth] = useState(0) // Track input width
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const boardRef = useRef(null)
  const previousBoardStateRef = useRef(null)
  const whiteStartTimeRef = useRef(null)
  const blackStartTimeRef = useRef(null)
  const whiteInitialTimeRef = useRef(180.0)
  const blackInitialTimeRef = useRef(180.0)
  const measureRef = useRef(null)

  const handlePieceMouseDown = (e, row, col) => {
    e.preventDefault()
    e.stopPropagation()

    const pieceKey = `${row},${col}`
    const piece = boardState?.board[pieceKey]

    // Determine if it's the player's turn
    const isPlayerTurn = boardState.current_turn === boardState.player_color

    // Allow dragging player's own pieces
    // Check available_moves for player's turn, premove_available_moves for opponent's turn
    const hasAvailableMoves = isPlayerTurn
      ? boardState.available_moves?.[pieceKey]?.length > 0
      : boardState.premove_available_moves?.[pieceKey]?.length > 0

    if (piece && piece.color === boardState.player_color && hasAvailableMoves) {
      // Track if this piece was already selected before we started dragging
      const wasAlreadySelected = selectedSquare?.row === row && selectedSquare?.col === col

      setDraggedPiece({
        row,
        col,
        piece,
        clientX: e.clientX,
        clientY: e.clientY,
        wasAlreadySelected
      })
      setSelectedSquare({ row, col })
    }
  }

  const handleMouseMove = (e) => {
    if (draggedPiece) {
      setDraggedPiece({
        ...draggedPiece,
        clientX: e.clientX,
        clientY: e.clientY
      })
    }
  }

  const handleMouseUp = (e) => {
    if (!draggedPiece || !boardRef.current) {
      setDraggedPiece(null)
      return
    }

    // Get the board's bounding rectangle
    const rect = boardRef.current.getBoundingClientRect()
    const squareSize = rect.width / 8

    // Calculate which square the mouse is over
    const isBlack = boardState.player_color === 'black'
    const relativeX = e.clientX - rect.left
    const relativeY = e.clientY - rect.top

    // Convert pixel coordinates to board coordinates
    const svgCol = Math.floor(relativeX / squareSize)
    const svgRow = Math.floor(relativeY / squareSize)

    // Check if within board bounds
    if (svgCol >= 0 && svgCol < 8 && svgRow >= 0 && svgRow < 8) {
      const boardRow = isBlack ? svgRow : 7 - svgRow
      const boardCol = isBlack ? 7 - svgCol : svgCol

      // Check if dropped on the same square it started from
      if (boardRow === draggedPiece.row && boardCol === draggedPiece.col) {
        // Toggle selection: if it was already selected before drag, deselect; otherwise keep selected
        if (draggedPiece.wasAlreadySelected) {
          setSelectedSquare(null)
        }
        // If it wasn't already selected, it's now selected (from handlePieceMouseDown), so keep it selected
        setDraggedPiece(null)
        return
      }

      // Check if this is a valid move
      const pieceKey = `${draggedPiece.row},${draggedPiece.col}`
      const isPlayerTurn = boardState.current_turn === boardState.player_color
      const availableMoves = isPlayerTurn
        ? (boardState.available_moves?.[pieceKey] || [])
        : (boardState.premove_available_moves?.[pieceKey] || [])
      const isValidMove = availableMoves.some(move => move.row === boardRow && move.col === boardCol)

      if (isValidMove) {
        // Check if this is a pawn promotion
        if (draggedPiece.piece.piece_type === 'pawn' && (boardRow === 0 || boardRow === 7)) {
          setPromotionPending({
            from: { row: draggedPiece.row, col: draggedPiece.col },
            to: { row: boardRow, col: boardCol }
          })
          setSelectedSquare(null)
          setDraggedPiece(null)
          return
        }

        // If it's not the player's turn, store as premove and show overlay
        if (!isPlayerTurn) {
          const premoveData = {
            from: { row: draggedPiece.row, col: draggedPiece.col },
            to: { row: boardRow, col: boardCol }
          }
          setPremove(premoveData)

          // Send premove to backend
          const moveData = {
            type: 'move',
            ...premoveData
          }
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(moveData))
            console.log('Premove sent:', moveData)
          }

          setSelectedSquare(null)
          setDraggedPiece(null)
          return
        }

        // Send the move
        const moveData = {
          type: 'move',
          from: { row: draggedPiece.row, col: draggedPiece.col },
          to: { row: boardRow, col: boardCol }
        }

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify(moveData))
          console.log('Move sent:', moveData)
        } else {
          alert('WebSocket is not connected')
        }

        setSelectedSquare(null)
      } else {
        // Invalid move - deselect the piece
        setSelectedSquare(null)
      }
    }

    setDraggedPiece(null)
  }

  const handleSquareClick = (row, col) => {
    // Ignore clicks if we're currently dragging
    if (draggedPiece) return

    const isPlayerTurn = boardState.current_turn === boardState.player_color

    if (!selectedSquare) {
      // First click: select the piece if it belongs to the player
      const pieceKey = `${row},${col}`
      const piece = boardState?.board[pieceKey]

      // Allow selection of player's pieces regardless of turn (for premoves)
      if (piece && piece.color === boardState.player_color) {
        setSelectedSquare({ row, col })
      }
    } else {
      // Second click: attempt to move
      const pieceKey = `${selectedSquare.row},${selectedSquare.col}`
      const piece = boardState?.board[pieceKey]

      // Check if the clicked square is a valid move (use premove_available_moves if not player's turn)
      const availableMoves = isPlayerTurn
        ? (boardState.available_moves?.[pieceKey] || [])
        : (boardState.premove_available_moves?.[pieceKey] || [])
      const isValidMove = availableMoves.some(move => move.row === row && move.col === col)

      // Check if this is a pawn promotion (pawn reaching last rank AND it's a valid move)
      if (piece?.piece_type === 'pawn' && (row === 0 || row === 7) && isValidMove) {
        // Show promotion dialog
        setPromotionPending({
          from: { row: selectedSquare.row, col: selectedSquare.col },
          to: { row, col }
        })
        setSelectedSquare(null)
        return
      }

      // If it's not the player's turn, store as premove and show overlay
      if (!isPlayerTurn && isValidMove) {
        const premoveData = {
          from: { row: selectedSquare.row, col: selectedSquare.col },
          to: { row, col }
        }
        setPremove(premoveData)

        // Send premove to backend
        const moveData = {
          type: 'move',
          ...premoveData
        }
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify(moveData))
          console.log('Premove sent:', moveData)
        }

        setSelectedSquare(null)
        return
      }

      const moveData = {
        type: 'move',
        from: { row: selectedSquare.row, col: selectedSquare.col },
        to: { row, col }
      }

      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(moveData))
        console.log('Move sent:', moveData)
      } else {
        alert('WebSocket is not connected')
      }

      // Clear selection
      setSelectedSquare(null)
    }
  }

  const handlePromotion = (pieceType) => {
    if (!promotionPending) return

    const moveData = {
      type: 'move',
      from: promotionPending.from,
      to: promotionPending.to,
      promotion: pieceType
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(moveData))
      console.log('Move sent:', moveData)
    } else {
      alert('WebSocket is not connected')
    }

    setPromotionPending(null)
  }

  const handlePlayClick = () => {
    setGameState('queue')
    connect()
  }

  const handlePlayAgain = () => {
    // Disconnect websocket
    if (wsRef.current) {
      wsRef.current.close()
    }
    // Reset state
    setGameOver(null)
    setBoardState(null)
    setSelectedSquare(null)
    setPromotionPending(null)
    setGameState('landing')
  }

  const connect = () => {
    const websocket = new WebSocket('ws://localhost:8000/ws')
    wsRef.current = websocket

    websocket.onopen = () => {
      console.log('WebSocket connected')
      // Send player name to backend
      const name = playerName.trim() || 'Guest'
      websocket.send(JSON.stringify({ type: 'set_name', name }))
    }

    websocket.onmessage = (event) => {
      console.log('Message received:', event.data)

      try {
        const data = JSON.parse(event.data)
        if (data.type === 'board_state') {
          const previousTurn = boardState?.current_turn
          setBoardState(data)
          setGameState('playing')

          // Set opponent name if provided
          if (data.opponent_name) {
            setOpponentName(data.opponent_name)
          }

          // Update timer initial values from server
          if (data.white_time !== undefined) {
            whiteInitialTimeRef.current = data.white_time
            // Only update display time for the non-active player
            if (data.current_turn !== 'white') {
              setWhiteTime(data.white_time)
            }
          }
          if (data.black_time !== undefined) {
            blackInitialTimeRef.current = data.black_time
            // Only update display time for the non-active player
            if (data.current_turn !== 'black') {
              setBlackTime(data.black_time)
            }
          }

          // Reset start time when turn changes or on initial board state
          if (previousTurn !== data.current_turn || !previousTurn) {
            if (data.current_turn === 'white') {
              whiteStartTimeRef.current = Date.now()
              blackStartTimeRef.current = null
            } else {
              blackStartTimeRef.current = Date.now()
              whiteStartTimeRef.current = null
            }
          }
        } else if (data.type === 'game_over') {
          setGameOver({
            result: data.result,
            is_checkmate: data.is_checkmate,
            is_stalemate: data.is_stalemate
          })
        }
      } catch (e) {
        // Text message (e.g., "Waiting for opponent...")
        // Stay in queue state
      }
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    websocket.onclose = () => {
      console.log('WebSocket disconnected')
      setGameState('landing')
      setBoardState(null)
    }
  }

  useEffect(() => {
    // Clear premove when board state changes (a move was made)
    if (boardState && premove && previousBoardStateRef.current) {
      // Only clear if the board state actually changed (a new move was made)
      const previousLastMove = previousBoardStateRef.current.last_move
      const currentLastMove = boardState.last_move

      // Check if a new move was made (last_move changed)
      const boardChanged = JSON.stringify(previousLastMove) !== JSON.stringify(currentLastMove)

      if (boardChanged) {
        // Check if the premove was executed by seeing if it matches the last move
        if (currentLastMove &&
            currentLastMove.from.row === premove.from.row &&
            currentLastMove.from.col === premove.from.col &&
            currentLastMove.to.row === premove.to.row &&
            currentLastMove.to.col === premove.to.col) {
          // Premove was executed, clear it
          setPremove(null)
        } else {
          // A different move was made, clear the premove
          setPremove(null)
        }
      }
    }

    // Update the previous board state
    if (boardState) {
      previousBoardStateRef.current = boardState
    }
  }, [boardState, premove])

  useEffect(() => {
    // Timer countdown logic using requestAnimationFrame for smooth updates
    let animationFrame = null

    const updateTimer = () => {
      if (!boardState || gameOver) return

      // Update white timer if it's white's turn
      if (boardState.current_turn === 'white' && whiteStartTimeRef.current) {
        const elapsed = (Date.now() - whiteStartTimeRef.current) / 1000
        const remaining = Math.max(0, whiteInitialTimeRef.current - elapsed)
        setWhiteTime(remaining)
      }

      // Update black timer if it's black's turn
      if (boardState.current_turn === 'black' && blackStartTimeRef.current) {
        const elapsed = (Date.now() - blackStartTimeRef.current) / 1000
        const remaining = Math.max(0, blackInitialTimeRef.current - elapsed)
        setBlackTime(remaining)
      }

      // Continue animation loop
      if (gameState === 'playing' && !gameOver) {
        animationFrame = requestAnimationFrame(updateTimer)
      }
    }

    const handleVisibilityChange = () => {
      if (document.hidden) {
        if (animationFrame) {
          cancelAnimationFrame(animationFrame)
          animationFrame = null
        }
      } else if (gameState === 'playing' && !gameOver) {
        updateTimer()
      }
    }

    if (gameState === 'playing' && boardState && !gameOver) {
      updateTimer()
      document.addEventListener('visibilitychange', handleVisibilityChange)
    }

    return () => {
      if (animationFrame) {
        cancelAnimationFrame(animationFrame)
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [gameState, boardState, gameOver])

  useEffect(() => {
    // Measure the width of the player name text synchronously
    if (measureRef.current) {
      const width = measureRef.current.offsetWidth
      // Use a small buffer to prevent clipping
      setInputWidth(width)
    }
  }, [playerName])

  // Initial measurement
  useEffect(() => {
    if (measureRef.current) {
      setInputWidth(measureRef.current.offsetWidth)
    }
  }, [])

  // Save player name to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('playerName', playerName)
  }, [playerName])

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      background: 'linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)',
      padding: '0'
    }}>
      {gameState === 'landing' && (
        <div style={{
          textAlign: 'center',
          color: 'white',
          fontFamily: "'Manrope', sans-serif"
        }}>
          <h1 style={{
            fontSize: '4rem',
            fontWeight: '700',
            marginBottom: '0rem',
            background: 'linear-gradient(135deg, #666666 0%, #999999 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>
            ReChess
          </h1>
          <p style={{
            fontSize: '1.5rem',
            fontWeight: '300',
            marginTop: '0',
            marginBottom: '2rem',
            color: '#888888'
          }}>
            Chess.... Redefined.
          </p>
          <button
            onClick={handlePlayClick}
            style={{
              fontSize: '1.25rem',
              fontWeight: '600',
              padding: '1rem 5rem',
              background: 'linear-gradient(135deg, #4a4a4a 0%, #6a6a6a 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '50px',
              cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s',
              boxShadow: '0 10px 25px rgba(74, 74, 74, 0.3)',
              marginBottom: '1rem'
            }}
            onMouseOver={(e) => {
              e.target.style.transform = 'translateY(-2px)'
              e.target.style.boxShadow = '0 15px 35px rgba(74, 74, 74, 0.4)'
            }}
            onMouseOut={(e) => {
              e.target.style.transform = 'translateY(0)'
              e.target.style.boxShadow = '0 10px 25px rgba(74, 74, 74, 0.3)'
            }}
          >
            Play
          </button>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            position: 'relative'
          }}>
            <label style={{
              fontSize: '1.25rem',
              fontWeight: '400',
              color: '#888888'
            }}>
              Playing as
            </label>
            {/* Hidden span to measure text width */}
            <span
              ref={measureRef}
              style={{
                position: 'absolute',
                visibility: 'hidden',
                fontSize: '1.25rem',
                fontWeight: '400',
                fontFamily: "'Manrope', sans-serif",
                whiteSpace: 'pre'
              }}
            >
              {playerName}
            </span>
            <input
              type="text"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handlePlayClick()
                }
              }}
              style={{
                fontSize: '1.25rem',
                fontWeight: '400',
                padding: '0.25rem 0',
                background: 'transparent',
                color: 'white',
                border: 'none',
                borderBottom: '2px solid #6a6a6a',
                width: playerName.trim() ? `${inputWidth + 2}px` : '60px',
                fontFamily: "'Manrope', sans-serif",
                outline: 'none',
                transition: 'border-bottom-color 0.2s'
              }}
              onFocus={(e) => {
                e.target.style.borderBottomColor = '#999999'
              }}
              onBlur={(e) => {
                e.target.style.borderBottomColor = '#6a6a6a'
              }}
            />
          </div>
        </div>
      )}

      {gameState === 'queue' && (
        <div style={{
          textAlign: 'center',
          color: 'white',
          fontFamily: "'Manrope', sans-serif"
        }}>
          <div style={{
            width: '80px',
            height: '80px',
            border: '8px solid rgba(106, 106, 106, 0.2)',
            borderTop: '8px solid #6a6a6a',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 2rem'
          }}></div>
          <p style={{
            fontSize: '1.5rem',
            fontWeight: '300',
            color: '#888888'
          }}>
            Finding opponent...
          </p>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {gameState === 'playing' && boardState && (
        <div
          style={{ position: 'relative', cursor: draggedPiece ? 'grabbing' : 'default' }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={() => setDraggedPiece(null)}
        >
          {/* Timer for opponent (top) */}
          <div style={{
            background: '#2b2b2b',
            padding: '1rem 1.5rem',
            marginBottom: '0',
            borderRadius: '4px 4px 0 0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontFamily: "'Manrope', sans-serif",
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem'
            }}>
              <div style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: '#ef4444'
              }} />
              <span style={{
                fontSize: '1.25rem',
                color: '#ffffff',
                fontWeight: '300'
              }}>{opponentName}</span>
            </div>
            <span style={{
              fontFamily: "'Manrope', sans-serif",
              fontSize: '1.5rem',
              fontWeight: '300',
              color: '#ffffff'
            }}>
              {formatTime(boardState.player_color === 'white' ? blackTime : whiteTime)}
            </span>
          </div>

          <div ref={boardRef}>
            {renderBoard(boardState, selectedSquare, handleSquareClick, gameOver !== null, draggedPiece, handlePieceMouseDown, premove)}
          </div>

          {/* Timer for player (bottom) */}
          <div style={{
            background: '#2b2b2b',
            padding: '1rem 1.5rem',
            marginTop: '0',
            borderRadius: '0 0 4px 4px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontFamily: "'Manrope', sans-serif",
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem'
            }}>
              <div style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: '#22c55e'
              }} />
              <span style={{
                fontSize: '1.25rem',
                color: '#ffffff',
                fontWeight: '300'
              }}>{playerName.trim() || 'Guest'}</span>
            </div>
            <span style={{
              fontFamily: "'Manrope', sans-serif",
              fontSize: '1.5rem',
              fontWeight: '300',
              color: '#ffffff'
            }}>
              {formatTime(boardState.player_color === 'white' ? whiteTime : blackTime)}
            </span>
          </div>

          {/* Render dragged piece at cursor position */}
          {draggedPiece && (
            <img
              src={getPieceSvgPath(draggedPiece.piece.piece_type, draggedPiece.piece.color)}
              style={{
                position: 'fixed',
                left: draggedPiece.clientX - 44,
                top: draggedPiece.clientY - 44,
                width: '88px',
                height: '88px',
                pointerEvents: 'none',
                zIndex: 1000,
                opacity: 0.8
              }}
              alt="dragged piece"
            />
          )}

          {/* Promotion modal */}
          {promotionPending && (
            <div
              onClick={() => setPromotionPending(null)}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                background: 'rgba(0, 0, 0, 0.7)',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: 'flex',
                  gap: '0.5rem'
                }}
              >
                {['queen', 'rook', 'bishop', 'knight'].map(pieceType => (
                  <button
                    key={pieceType}
                    onClick={() => handlePromotion(pieceType)}
                    style={{
                      background: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      padding: '0.5rem',
                      cursor: 'pointer',
                      transition: 'transform 0.2s',
                      width: '60px',
                      height: '60px'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.transform = 'scale(1.1)'
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.transform = 'scale(1)'
                    }}
                  >
                    <img
                      src={getPieceSvgPath(pieceType, boardState.player_color)}
                      alt={pieceType}
                      style={{ width: '100%', height: '100%' }}
                    />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Game over overlay */}
          {gameOver && (
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              background: 'rgba(0, 0, 0, 0.8)',
              borderRadius: '4px'
            }}>
              <div style={{
                background: 'white',
                padding: '2rem',
                borderRadius: '8px',
                textAlign: 'center',
                fontFamily: "'Manrope', sans-serif"
              }}>
                <h2 style={{
                  fontSize: '2rem',
                  fontWeight: '700',
                  marginBottom: '1rem',
                  color: '#2d2d2d'
                }}>
                  Game Over
                </h2>
                <p style={{
                  fontSize: '1.25rem',
                  fontWeight: '500',
                  color: '#6a6a6a',
                  marginBottom: '0.5rem'
                }}>
                  {gameOver.result}
                </p>
                <p style={{
                  fontSize: '1rem',
                  color: '#666',
                  fontStyle: 'italic',
                  marginBottom: '1.5rem'
                }}>
                  {gameOver.is_checkmate ? 'Checkmate' : gameOver.is_stalemate ? 'Stalemate' : ''}
                </p>
                <button
                  onClick={handlePlayAgain}
                  style={{
                    fontSize: '1.1rem',
                    fontWeight: '600',
                    padding: '0.75rem 2rem',
                    background: 'linear-gradient(135deg, #4a4a4a 0%, #6a6a6a 100%)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '50px',
                    cursor: 'pointer',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    boxShadow: '0 8px 20px rgba(74, 74, 74, 0.3)'
                  }}
                  onMouseOver={(e) => {
                    e.target.style.transform = 'translateY(-2px)'
                    e.target.style.boxShadow = '0 12px 28px rgba(74, 74, 74, 0.4)'
                  }}
                  onMouseOut={(e) => {
                    e.target.style.transform = 'translateY(0)'
                    e.target.style.boxShadow = '0 8px 20px rgba(74, 74, 74, 0.3)'
                  }}
                >
                  Play again?
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
