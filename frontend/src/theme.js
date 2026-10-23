import { createTheme } from '@mui/material/styles'

const APP_BAR_HEIGHT = '58px'
const BOARD_BAR_HEIGHT = '50px'
const MAP_INFO_BAR_HEIGHT = '50px'
const BOARD_CONTENT_HEIGHT = `calc(100vh - ${APP_BAR_HEIGHT} - ${BOARD_BAR_HEIGHT})`
const LIST_CONTENT_HEIGHT = `calc(100vh - ${APP_BAR_HEIGHT} - ${BOARD_BAR_HEIGHT}) `
const LIST_CARD_HEIGHT = `calc(100vh - ${APP_BAR_HEIGHT} - ${BOARD_BAR_HEIGHT} - ${MAP_INFO_BAR_HEIGHT} - 75px) `
// Create a theme instance.
const theme = createTheme({
  mapCustom: {
    appBarHeight: APP_BAR_HEIGHT,
    boardBarHeight: BOARD_BAR_HEIGHT,
    mapInfoBarHeight: MAP_INFO_BAR_HEIGHT,
    boardContentHeight: BOARD_CONTENT_HEIGHT,
    listContentHeight: LIST_CONTENT_HEIGHT,
    listCardHeight: LIST_CARD_HEIGHT
  },
  cssVariables: {
    colorSchemeSelector: 'class'
  },
  colorSchemes: {
    dark: true,
    light: true
  },
  palette: {},
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        '*::-webkit-scrollbar': {
          width: 6
        },
        '*::-webkit-scrollbar-thumb': {
          backgroundColor: '#dcd0da',
          borderRadius: 3
        },
        '*::-webkit-scrollbar-thumb:hover': {
          backgroundColor: '#bfc2df'
        },
        '*::-webkit-scrollbar-track': {
          backgroundColor: 'transparent'
        }
      }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderWidth: '0.5px',
         
        },
        startIcon: {
          marginRight: '5px'
        },
        endIcon: {
          marginLeft: '2px'
        }
      }
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          
        }
      }
    }
  }
})

export default theme
