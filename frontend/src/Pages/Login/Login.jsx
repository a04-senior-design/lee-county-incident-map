import Box from '@mui/material/Box'
import AppBar from '../../components/AppBar/AppBar'
import Paper from '@mui/material/Paper'
import ModeSelect from '../../components/ModeSelect/ModeSelect'
import Typography from '@mui/material/Typography'
import TextField from '@mui/material/TextField'
import CarAnimation from '../../assets/carAnimation.svg'
import Link from '@mui/material/Link'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import InputAdornment from '@mui/material/InputAdornment'
import SearchIcon from '@mui/icons-material/Search'
import { useState, useContext } from 'react'
import VisibilityIcon from '@mui/icons-material/Visibility'
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff'
import AppAlert from '../../components/AppAlert/AppAlert'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../Context/AuthContext'
import LeftLoginPage from './LeftLoginPage/LeftLoginPage'
import * as React from 'react'
import { useTheme } from '@mui/material/styles'
import MobileStepper from '@mui/material/MobileStepper'
import KeyboardArrowLeft from '@mui/icons-material/KeyboardArrowLeft'
import KeyboardArrowRight from '@mui/icons-material/KeyboardArrowRight'
const url = import.meta.env.VITE_API_BASE_URL
function Login() {
  const theme = useTheme()
  const [activeStep, setActiveStep] = React.useState(0)

  const handleNext = () => {
    setActiveStep((prevActiveStep) => prevActiveStep + 1)
  }

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1)
  }
  const { setSession } = useAuth()
  const navigate = useNavigate()
  const [loginOn, setLoginOn] = useState(true)
  const [userLogin, setUserLogin] = useState({
    email: '',
    password: ''
  })
  const [userSignup, setUserSignup] = useState({
    name: '',
    email: '',
    password: ''
  })
  // --------Password------------------------------------------
  const [visible, setVisible] = useState(false)
  const [passwordLength, setPasswordLength] = useState(null)

  // --------Alert------------------------------------------
  const [AlertContent, SetAlertContent] = useState({
    open: false,
    vertical: 'bottom',
    horizontal: 'right',
    severity: '',
    content: ''
  })
  // --------Function------------------------------------------
  const handleLogin = async () => {
    try {
      const res = await fetch(`${url}/auth/login`, {
        credentials: 'include',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email: userLogin.email,
          password: userLogin.password
        })
      })
      const data = await res.json()

      if (!res.ok) throw new Error(data.error || 'Login failed')
      SetAlertContent((prev) => ({
        ...prev,
        open: true,
        severity: 'success',
        content: 'User login successfully'
      }))

      setSession(data.user, data.access_token)
      setUserLogin({ email: '', password: '' })
      navigate('/')
    } catch (error) {
      SetAlertContent((prev) => ({
        ...prev,
        open: true,
        severity: 'error',
        content: error.message
      }))
    }
  }
  const handleSignup = async () => {
    if (passwordLength < 8) {
      return
    }
    try {
      const res = await fetch(`${url}/auth/register`, {
        credentials: 'include',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email: userSignup.email,
          password: userSignup.password
        })
      })
      const data = await res.json()

      if (!res.ok) throw new Error(data.error || 'Signup failed')
      SetAlertContent((prev) => ({
        ...prev,
        open: true,
        severity: 'success',
        content: 'User registed successfully'
      }))
      setSession(data.user, data.access_token)

      setUserSignup({ name: '', email: '', password: '' })
      setPasswordLength(null)
      navigate('/')
    } catch (error) {
      SetAlertContent((prev) => ({
        ...prev,
        open: true,
        severity: 'error',
        content: error.message
      }))
    }
  }
  return (
    <Box>
      <Box
        sx={{
          width: '100vw',
          height: (theme) => `calc(100vh)`,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: ''
        }}
      >
        <Paper
          elevation={24}
          sx={{
            width: '100vw',
            height: '100vh',
            display: 'flex',
            position: 'fixed',
            backgroundColor: '#104862',
            zIndex: 2
          }}
        ></Paper>
        <Paper
          elevation={24}
          sx={{
            width: '80vw',
            height: '87.5vh',
            display: 'flex',
            position: 'fixed',
            backgroundColor: '#46B1E1',
            zIndex: 2,
            top: '6.5%',
            '&:hover': {
              transform: 'scale(1.02)'
            },
            transition: 'ease-in-out 0.3s'
          }}
        ></Paper>
        <Paper
          elevation={24}
          sx={{
            width: '60vw',
            height: '75vh',
            display: 'flex',
            position: 'fixed',
            backgroundColor: '#C1E5F5',
            zIndex: 9,
            top: '12.5%',
            '&:hover': {
              transform: 'scale(1.02)'
            },
            transition: 'ease-in-out 0.3s'
          }}
        ></Paper>
        <Paper
          elevation={18}
          sx={{
            width: 'clamp(390px, 65vw,1000px)',
            height: '62.5vh',
            display: 'flex',
            zIndex: 10,
            '&:hover': {
              transform: 'scale(1.02)'
            },
            transition: 'ease-in-out 0.3s'
          }}
        >
          <Box
            sx={{
              borderRadius: '4px',
              height: '100%',
              flexGrow: 1,
              p: 4
            }}
          >
            <LeftLoginPage />
          </Box>
          <Paper
            sx={{
              height: '100%',
              width: '42%',
              minWidth: '400px',
              display: 'flex',
              justifyContent: 'center'
            }}
          >
            <Box>
              <Box sx={{ marginTop: '50px', marginBottom: '30px' }}>
                <Typography
                  variant='span'
                  sx={{ fontWeight: 500, fontSize: '24px' }}
                >
                  Welcome to
                </Typography>

                <Typography
                  variant='span'
                  sx={[
                    {
                      ml: '4px',
                      fontWeight: 500,
                      fontSize: '32px',
                      color: (theme) => theme.palette.primary.main
                    },
                    (theme) =>
                      theme.applyStyles('dark', {
                        color: (theme) => theme.palette.primary.light
                      })
                  ]}
                >
                  PAIM
                </Typography>
              </Box>
              <Typography
                variant='span'
                sx={{ fontWeight: 500, fontSize: '24px' }}
              >
                {loginOn ? 'Login' : 'Signup'}
              </Typography>
              <Box
                sx={{
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  mt: 1
                }}
              >
                {loginOn ? (
                  <>
                    {' '}
                    <TextField
                      id='login-email-input'
                      label='Email'
                      type='text'
                      autoComplete='off'
                      value={userLogin.email}
                      onChange={(e) => {
                        setUserLogin((prev) => ({
                          ...prev,
                          email: e.target.value
                        }))
                      }}
                    />
                    <TextField
                      id='login-password-input'
                      label='Password'
                      autoComplete='current-password'
                      type={visible ? 'text' : 'password'}
                      value={userLogin.password}
                      onChange={(e) => {
                        setUserLogin((prev) => ({
                          ...prev,
                          password: e.target.value
                        }))
                      }}
                      slotProps={{
                        input: {
                          endAdornment: (
                            <InputAdornment position='end'>
                              {visible ? (
                                <VisibilityIcon
                                  onClick={() => {
                                    setVisible(false)
                                  }}
                                />
                              ) : (
                                <VisibilityOffIcon
                                  onClick={() => {
                                    setVisible(true)
                                  }}
                                />
                              )}
                            </InputAdornment>
                          )
                        }
                      }}
                    />
                  </>
                ) : (
                  <>
                    {' '}
                    <TextField
                      id='standard-usrname-input'
                      label='Your name'
                      type='text'
                      autoComplete='off'
                      value={userSignup.name}
                      onChange={(e) =>
                        setUserSignup((prev) => ({
                          ...prev,
                          name: e.target.value
                        }))
                      }
                    />
                    <TextField
                      id='signup-email-input'
                      label='Email'
                      type='text'
                      autoComplete='current-password'
                      value={userSignup.email}
                      onChange={(e) =>
                        setUserSignup((prev) => ({
                          ...prev,
                          email: e.target.value
                        }))
                      }
                    />
                    <TextField
                      id='signup-password-input'
                      label='Password'
                      type={visible ? 'text' : 'password'}
                      slotProps={{
                        input: {
                          endAdornment: (
                            <InputAdornment position='end'>
                              {visible ? (
                                <VisibilityIcon
                                  onClick={() => {
                                    setVisible(false)
                                  }}
                                />
                              ) : (
                                <VisibilityOffIcon
                                  onClick={() => {
                                    setVisible(true)
                                  }}
                                />
                              )}
                            </InputAdornment>
                          )
                        }
                      }}
                      autoComplete='current-password'
                      value={userSignup.password}
                      onChange={(e) => {
                        setUserSignup((prev) => ({
                          ...prev,
                          password: e.target.value
                        }))
                        setPasswordLength(e.target.value.length)
                      }}
                    />
                  </>
                )}
              </Box>
              <AppAlert
                AlertContent={AlertContent}
                SetAlertContent={SetAlertContent}
              />
              <Box sx={{ marginTop: '10px' }}>
                <Link sx={{ cursor: 'pointer' }}>Fogot password</Link>
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1,
                    marginBottom: '16px'
                  }}
                >
                  <Button
                    variant='contained'
                    onClick={() => {
                      loginOn ? handleLogin() : handleSignup()
                    }}
                  >
                    {loginOn ? 'Login' : 'Signup'}
                  </Button>
                  <Button
                    variant='outlined'
                    onClick={() => {
                      setLoginOn(!loginOn)
                      setVisible(false)
                    }}
                  >
                    {loginOn ? 'Create new account' : 'Already has account'}
                  </Button>
                </Box>
                <Link
                  sx={{
                    cursor: 'pointer',
                    display: 'flex',
                    width: 'fit-content',
                    margin: '0 auto 10px'
                  }}
                  onClick={() => navigate('/')}
                >
                  Continue as Guest
                </Link>
              </Box>

              <Alert
                severity={passwordLength >= 8 ? 'success' : 'warning'}
                sx={{
                  width: '250px',
                  height: '80px',
                  display: 'flex',

                  opacity: loginOn ? 0 : 100,
                  transition: 'linear 0.3s'
                }}
              >
                <Typography>The password must be 8 characters long.</Typography>
              </Alert>
            </Box>
          </Paper>
        </Paper>
      </Box>
    </Box>
  )
}

export default Login
