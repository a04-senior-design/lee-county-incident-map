import Box from '@mui/material/Box'
import AppBar from '../../components/AppBar/AppBar'
import Paper from '@mui/material/Paper'
import ModeSelect from '../../components/ModeSelect/ModeSelect'
import Typography from '@mui/material/Typography'
import TextField from '@mui/material/TextField'
import CarAnimation from '../../assets/carAnimation.svg'
function Login() {
  return (
    <Box>
      <AppBar />
      <ModeSelect />
      <Box
        sx={{
          width: '100vw',
          height: (theme) => `calc(100vh - ${theme.mapCustom.appBarHeight})`,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center'
        }}
      >
        <Paper
          elevation={3}
          sx={{
            width: 'clamp(390px, 70vw,1200px)',
            height: '70vh',
            display: 'flex'
          }}
        >
          <Box
            sx={{
              borderRadius: '4px',
              height: '100%',
              flexGrow: 1,
              bgcolor: (theme) => theme.palette.error.main
            }}
          >
            <Box
              component='object'
              type='image/svg+xml'
              data={CarAnimation}
              aria-label='Animated car'
              sx={{
                width: '100%',
                height: '100%',
                objectFit: 'contain'
              }}
            />
          </Box>
          <Paper sx={{ height: '100%', width: '40%' }}>
            <Box>
              <Box>
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

              <Box sx={{ width: '100%' }}>
                <TextField
                  id='standard-usrname-input'
                  label='username'
                  type='text'
                  autoComplete='off'
                  size='small'
                />
                <TextField
                  id='standard-password-input'
                  label='Password'
                  type='password'
                  autoComplete='current-password'
                  size='small'
                />
              </Box>
            </Box>
          </Paper>
        </Paper>
      </Box>
    </Box>
  )
}

export default Login
