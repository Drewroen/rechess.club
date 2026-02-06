import { useState, useEffect, useRef } from 'react'
import './App.css'
import { getPieceSvgPath } from './services/chessPieces'

// Helper function to render board with checkered pattern
function renderBoard(boardState, selectedSquare, onSquareClick) {
  if (!boardState || !boardState.board) return null

  const board = boardState.board
  const squareSize = 60 // Size of each square in pixels
  const isBlack = boardState.player_color === 'black'

  return (
    <svg
      width={squareSize * 8}
      height={squareSize * 8}
      viewBox={`0 0 ${squareSize * 8} ${squareSize * 8}`}
      style={{ border: '2px solid #333' }}
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
          let fillColor = isLightSquare ? '#f0d9b5' : '#b58863'

          // Highlight selected square
          if (selectedSquare && selectedSquare.row === boardRow && selectedSquare.col === boardCol) {
            fillColor = '#7fc97f'
          }

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

      {/* Render pieces on top of the board */}
      {Object.entries(board).map(([key, piece]) => {
        const [row, col] = key.split(',').map(Number)
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
          />
        )
      })}
    </svg>
  )
}

function App() {
  const [boardState, setBoardState] = useState(null)
  const [selectedSquare, setSelectedSquare] = useState(null) // { row, col } or null
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const handleSquareClick = (row, col) => {
    if (!selectedSquare) {
      // First click: select the piece
      setSelectedSquare({ row, col })
    } else {
      // Second click: attempt to move
      const moveData = {
        type: 'move',
        from: { row: selectedSquare.row, col: selectedSquare.col },
        to: { row, col }
      }

      // Check if this is a pawn promotion (pawn reaching last rank)
      const pieceKey = `${selectedSquare.row},${selectedSquare.col}`
      const piece = boardState?.board[pieceKey]

      if (piece?.piece_type === 'pawn' && (row === 0 || row === 7)) {
        // Simple promotion - default to queen for now
        moveData.promotion = 'queen'
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


  useEffect(() => {
    let isMounted = true

    const connect = () => {
      if (!isMounted) return

      const websocket = new WebSocket('ws://localhost:8000/ws')
      wsRef.current = websocket

      websocket.onopen = () => {
        if (!isMounted) return
        console.log('WebSocket connected')
      }

      websocket.onmessage = (event) => {
        if (!isMounted) return
        console.log('Message received:', event.data)

        try {
          const data = JSON.parse(event.data)
          if (data.type === 'board_state') {
            setBoardState(data)
          }
        } catch (e) {
          // Ignore non-JSON messages
        }
      }

      websocket.onerror = (error) => {
        if (!isMounted) return
        console.error('WebSocket error:', error)
      }

      websocket.onclose = () => {
        if (!isMounted) return
        console.log('WebSocket disconnected')

        // Attempt to reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMounted) {
            console.log('Attempting to reconnect...')
            connect()
          }
        }, 3000)
      }
    }

    connect()

    // Cleanup on unmount
    return () => {
      isMounted = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return (
    <>
      {boardState && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
          {renderBoard(boardState, selectedSquare, handleSquareClick)}
        </div>
      )}
    </>
  )
}

export default App
