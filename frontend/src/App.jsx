
// import LandingPage from "./components/LandingPage";
import MapPage from './components/MapPage'
import Container from '@mui/material/Container'
function App() {
  return (
    <Container disableGutters maxWidth={false} sx={{ height: '100vh' }}>
      <MapPage />
    </Container>
  )
}

export default App
