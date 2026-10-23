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
import Test from './Pages/Login/Testtt.jsx'
// ‼️ import dates styles after core package styles
import '@mantine/dates/styles.css'
import AuthProvider from './Context/AuthProvider.jsx'
const router = createBrowserRouter([
  { path: '/', element: <App /> },
  { path: '/login', element: <Login /> },
  { path: '/test', element: <Test /> }
])
createRoot(document.getElementById('root')).render(
  <AuthProvider>
    <MantineProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <RouterProvider router={router} />
      </ThemeProvider>
    </MantineProvider>
  </AuthProvider>
)
