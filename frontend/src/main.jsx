import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import theme from './theme'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Login from './Pages/Login/Login.jsx'
import { MantineProvider } from '@mantine/core'
import '@mantine/core/styles.css'
// ‼️ import dates styles after core package styles
import '@mantine/dates/styles.css'
const router = createBrowserRouter([
  { path: '/', element: <App /> },
  { path: '/login', element: <Login /> }
])
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MantineProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <RouterProvider router={router} />
      </ThemeProvider>
    </MantineProvider>
  </StrictMode>
)
