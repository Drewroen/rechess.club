import { useState, useEffect, useRef } from 'react'
import './App.css'
import { getPieceSvgPath } from './services/chessPieces'

// Helper function to render board with checkered pattern
function renderBoard(boardState, selectedSquare, onSquareClick, isGameOver = false) {
  if (!boardState || !boardState.board) return null

  const board = boardState.board
  const squareSize = 60 // Size of each square in pixels
  const isBlack = boardState.player_color === 'black'

  // Get available moves for the selected piece
  const availableMoves = selectedSquare && boardState.available_moves
    ? boardState.available_moves[`${selectedSquare.row},${selectedSquare.col}`] || []
    : []

  return (
    <svg
      width={squareSize * 8}
      height={squareSize * 8}
      viewBox={`0 0 ${squareSize * 8} ${squareSize * 8}`}
      style={{
        border: '2px solid #333',
        filter: isGameOver ? 'grayscale(100%)' : 'none'
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
          const fillColor = isLightSquare ? '#f0d9b5' : '#b58863'

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
        const centerX = x + squareSize / 2
        const centerY = y + squareSize / 2

        // Check if this move captures a piece
        const pieceKey = `${move.row},${move.col}`
        const isCapture = board[pieceKey] !== undefined

        if (isCapture) {
          // Render capture indicator (ring around the piece)
          return (
            <g key={`move-${idx}`}>
              <defs>
                <radialGradient id={`capture-gradient-${idx}`}>
                  <stop offset="0%" stopColor="transparent" />
                  <stop offset="79%" stopColor="transparent" />
                  <stop offset="80%" stopColor="rgba(20, 85, 0, 0.3)" />
                  <stop offset="100%" stopColor="rgba(20, 85, 0, 0.3)" />
                </radialGradient>
              </defs>
              <rect
                x={x}
                y={y}
                width={squareSize}
                height={squareSize}
                fill={`url(#capture-gradient-${idx})`}
                style={{ pointerEvents: 'none' }}
              />
            </g>
          )
        } else {
          // Render regular move indicator (small circle)
          const radius = squareSize * 0.15
          return (
            <circle
              key={`move-${idx}`}
              cx={centerX}
              cy={centerY}
              r={radius}
              fill="rgba(20, 85, 30, 0.5)"
              style={{ pointerEvents: 'none' }}
            />
          )
        }
      })}

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
  const [gameState, setGameState] = useState('landing') // 'landing', 'queue', 'playing'
  const [promotionPending, setPromotionPending] = useState(null) // { from, to } or null
  const [gameOver, setGameOver] = useState(null) // { result, is_checkmate, is_stalemate } or null
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const handleSquareClick = (row, col) => {
    if (!selectedSquare) {
      // First click: select the piece only if it belongs to the player and has available moves
      const pieceKey = `${row},${col}`
      const piece = boardState?.board[pieceKey]

      // Only select if it's the player's piece and it has available moves
      if (piece && piece.color === boardState.player_color && boardState.available_moves?.[pieceKey]?.length > 0) {
        setSelectedSquare({ row, col })
      }
    } else {
      // Second click: attempt to move
      const pieceKey = `${selectedSquare.row},${selectedSquare.col}`
      const piece = boardState?.board[pieceKey]

      // Check if this is a pawn promotion (pawn reaching last rank)
      if (piece?.piece_type === 'pawn' && (row === 0 || row === 7)) {
        // Show promotion dialog
        setPromotionPending({
          from: { row: selectedSquare.row, col: selectedSquare.col },
          to: { row, col }
        })
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
    }

    websocket.onmessage = (event) => {
      console.log('Message received:', event.data)

      try {
        const data = JSON.parse(event.data)
        if (data.type === 'board_state') {
          setBoardState(data)
          setGameState('playing')
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
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)'
    }}>
      {gameState === 'landing' && (
        <div style={{
          textAlign: 'center',
          color: 'white',
          fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
        }}>
          <h1 style={{
            fontSize: '4rem',
            fontWeight: '700',
            marginBottom: '1rem',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>
            ReChess
          </h1>
          <p style={{
            fontSize: '1.5rem',
            fontWeight: '300',
            marginBottom: '3rem',
            color: '#a0aec0'
          }}>
            Chess Redefined
          </p>
          <button
            onClick={handlePlayClick}
            style={{
              fontSize: '1.25rem',
              fontWeight: '600',
              padding: '1rem 3rem',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '50px',
              cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s',
              boxShadow: '0 10px 25px rgba(102, 126, 234, 0.3)'
            }}
            onMouseOver={(e) => {
              e.target.style.transform = 'translateY(-2px)'
              e.target.style.boxShadow = '0 15px 35px rgba(102, 126, 234, 0.4)'
            }}
            onMouseOut={(e) => {
              e.target.style.transform = 'translateY(0)'
              e.target.style.boxShadow = '0 10px 25px rgba(102, 126, 234, 0.3)'
            }}
          >
            Play
          </button>
        </div>
      )}

      {gameState === 'queue' && (
        <div style={{
          textAlign: 'center',
          color: 'white',
          fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
        }}>
          <div style={{
            width: '80px',
            height: '80px',
            border: '8px solid rgba(102, 126, 234, 0.2)',
            borderTop: '8px solid #667eea',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 2rem'
          }}></div>
          <p style={{
            fontSize: '1.5rem',
            fontWeight: '300',
            color: '#a0aec0'
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
        <div style={{ position: 'relative' }}>
          {renderBoard(boardState, selectedSquare, handleSquareClick, gameOver !== null)}

          {/* Promotion modal */}
          {promotionPending && (
            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              background: 'rgba(0, 0, 0, 0.7)',
              borderRadius: '4px'
            }}>
              <div style={{
                display: 'flex',
                gap: '0.5rem'
              }}>
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
                fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
              }}>
                <h2 style={{
                  fontSize: '2rem',
                  fontWeight: '700',
                  marginBottom: '1rem',
                  color: '#1a1a2e'
                }}>
                  Game Over
                </h2>
                <p style={{
                  fontSize: '1.25rem',
                  fontWeight: '500',
                  color: '#667eea',
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
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '50px',
                    cursor: 'pointer',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    boxShadow: '0 8px 20px rgba(102, 126, 234, 0.3)'
                  }}
                  onMouseOver={(e) => {
                    e.target.style.transform = 'translateY(-2px)'
                    e.target.style.boxShadow = '0 12px 28px rgba(102, 126, 234, 0.4)'
                  }}
                  onMouseOut={(e) => {
                    e.target.style.transform = 'translateY(0)'
                    e.target.style.boxShadow = '0 8px 20px rgba(102, 126, 234, 0.3)'
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
