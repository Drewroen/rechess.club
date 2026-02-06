/**
 * Service for retrieving chess piece SVG paths
 */

const PIECE_SETS = {
  STANDARD: 'standard',
  FAIRY: 'fairy'
};

const COLORS = {
  WHITE: 'white',
  BLACK: 'black'
};

/**
 * Get the SVG path for a specific chess piece
 * @param {string} pieceType - The type of piece (e.g., 'king', 'queen', 'pawn')
 * @param {string} color - The color of the piece ('white' or 'black')
 * @param {string} pieceSet - The piece set to use ('standard' or 'fairy')
 * @returns {string} The path to the SVG file
 */
export function getPieceSvgPath(pieceType, color = COLORS.WHITE, pieceSet = PIECE_SETS.STANDARD) {
  return `/chess-pieces/${pieceSet}/${pieceType}_${color}.svg`;
}

/**
 * Get SVG paths for all pieces of a specific color in a set
 * @param {string} color - The color of the pieces ('white' or 'black')
 * @param {string} pieceSet - The piece set to use ('standard' or 'fairy')
 * @returns {Object} Object with piece types as keys and SVG paths as values
 */
export function getAllPiecesForColor(color = COLORS.WHITE, pieceSet = PIECE_SETS.STANDARD) {
  const standardPieces = ['king', 'queen', 'rook', 'bishop', 'knight', 'pawn'];
  const fairyPieces = [
    'archbishop', 'dragon', 'ship', 'chancellor', 'elephant',
    'mann', 'zebra', 'giraffe', 'fool', 'unicorn', 'wizard', 'commoner'
  ];

  const pieces = pieceSet === PIECE_SETS.FAIRY ? fairyPieces : standardPieces;

  return pieces.reduce((acc, pieceType) => {
    acc[pieceType] = getPieceSvgPath(pieceType, color, pieceSet);
    return acc;
  }, {});
}

/**
 * Get all available piece SVG paths for a given piece set
 * @param {string} pieceSet - The piece set to use ('standard' or 'fairy')
 * @returns {Object} Object with 'white' and 'black' keys containing piece SVG paths
 */
export function getAllPieces(pieceSet = PIECE_SETS.STANDARD) {
  return {
    white: getAllPiecesForColor(COLORS.WHITE, pieceSet),
    black: getAllPiecesForColor(COLORS.BLACK, pieceSet)
  };
}

export { PIECE_SETS, COLORS };
