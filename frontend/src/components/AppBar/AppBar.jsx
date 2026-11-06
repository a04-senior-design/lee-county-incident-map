import { useState } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Tooltip from '@mui/material/Tooltip'
import IconButton from '@mui/material/IconButton'
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone'
import Badge from '@mui/material/Badge'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Avatar from '@mui/material/Avatar'
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts'
import LogoutIcon from '@mui/icons-material/Logout'
import AccountCircleIcon from '@mui/icons-material/AccountCircle'
import Divider from '@mui/material/Divider'
import Page from '../../assets/icon/pageIcon.svg?react'
import SvgIcon from '@mui/material/SvgIcon'
import Button from '@mui/material/Button'
import InfoIcon from '@mui/icons-material/Info'
import HomeIcon from '@mui/icons-material/Home'
import LocalLibraryIcon from '@mui/icons-material/LocalLibrary'
import MessageIcon from '@mui/icons-material/Message'
import Link from '@mui/material/Link'
import { useAuth } from '../../Context/AuthContext'
import { useNavigate } from 'react-router-dom'
import AppNoti from '../AppNoti/AppNoti'
function AppBar({ setAccountPop, accountPop, setIsPulled, CATEGORY_COLORS }) {
  const { logout, user } = useAuth()
  const navigate = useNavigate()
  const [anchorEl, setAnchorEl] = useState(null)
  const open = Boolean(anchorEl)
  const handleClick = (event) => {
    setAnchorEl(event.currentTarget)
  }
  const handleClose = () => {
    setAnchorEl(null)
  }
  return (
    <Box
      sx={[
        {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          height: (theme) => theme.mapCustom.appBarHeight,
          bgcolor: 'primary.main',
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: (theme) => theme.palette.grey[600]
          },

          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: (theme) => theme.palette.grey[800]
          },

          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: (theme) => theme.palette.primary.main
          }
        },
        (theme) =>
          theme.applyStyles('dark', {
            backgroundColor: 'rgba(20, 20, 41, 0.92)'
          })
      ]}
    >
      <Box
        sx={{
          display: 'flex',
          gap: 5,
          alignItems: 'center',
          cursor: 'pointer'
        }}
      >
        <Box sx={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
          <SvgIcon
            component={Page}
            inheritViewBox
            sx={{ color: 'white', width: 24, height: 24 }}
          />
          <Typography
            variant='span'
            sx={{ fontSize: '20px', fontWeight: 'bold', color: 'white' }}
          >
            LCIM
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Button
            sx={[
              { color: 'white' },
              (theme) =>
                theme.applyStyles('dark', {
                  color: 'rgba(255, 255, 255, 0.92)'
                })
            ]}
            startIcon={<LocalLibraryIcon />}
          >
            Resources
          </Button>
          <Button
            sx={[
              { color: 'white' },
              (theme) =>
                theme.applyStyles('dark', {
                  color: 'rgba(255, 255, 255, 0.92)'
                })
            ]}
            startIcon={<InfoIcon />}
          >
            About
          </Button>
          <Button
            sx={[
              { color: 'white' },
              (theme) =>
                theme.applyStyles('dark', {
                  color: 'rgba(255, 255, 255, 0.92)'
                })
            ]}
            startIcon={<MessageIcon />}
          >
            Feedback
          </Button>
        </Box>
      </Box>
      {user ? (
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <AppNoti CATEGORY_COLORS={CATEGORY_COLORS} />

          <Box sx={{ ml: 1.5, cursor: 'pointer' }}>
            <Avatar
              sx={{ width: 32, height: 32, bgcolor: 'error.light' }}
              id='basic-button'
              aria-controls={open ? 'basic-menu' : undefined}
              aria-haspopup='true'
              aria-expanded={open ? 'true' : undefined}
              onClick={handleClick}
              alt='Remy Sharp'
              src='/static/images/avatar/1.jpg'
            />
            <Menu
              id='basic-menu'
              anchorEl={anchorEl}
              open={open}
              onClose={handleClose}
              slotProps={{
                list: {
                  'aria-labelledby': 'basic-button'
                }
              }}
            >
              <MenuItem
                onClick={() => {
                  setAccountPop(true)
                  handleClose()
                  setIsPulled(false)
                }}
              >
                <ManageAccountsIcon sx={{ marginRight: 1 }} />
                My account
              </MenuItem>
              <MenuItem
                onClick={async () => {
                  await logout()
                  navigate('/login')
                }}
              >
                <LogoutIcon sx={{ marginRight: 1 }} />
                Logout
              </MenuItem>
            </Menu>
          </Box>
        </Box>
      ) : (
        <Link
          sx={{ cursor: 'pointer', color: 'white', fontWeight: 600 }}
          onClick={() => navigate('/login')}
        >
          {' '}
          Sign in/ Sign up
        </Link>
      )}
    </Box>
  )
}

export default AppBar
