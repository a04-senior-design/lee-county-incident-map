import { useState } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Tooltip from '@mui/material/Tooltip'
import IconButton from '@mui/material/IconButton'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone'
import Badge from '@mui/material/Badge'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Avatar from '@mui/material/Avatar'
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts'
import LogoutIcon from '@mui/icons-material/Logout'
import AccountCircleIcon from '@mui/icons-material/AccountCircle'
import Divider from '@mui/material/Divider'
import Page from '/Users/dangk/lee-county-incident-map/frontend/src/assets/icon/pageIcon.svg?react'
import SvgIcon from '@mui/material/SvgIcon'
import Button from '@mui/material/Button'
import InfoIcon from '@mui/icons-material/Info'
import HomeIcon from '@mui/icons-material/Home'
import LocalLibraryIcon from '@mui/icons-material/LocalLibrary'
import MessageIcon from '@mui/icons-material/Message';
function AppBar() {
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
      <Box sx={{ display: 'flex', gap: 5, alignItems: 'center', cursor:'pointer' }}>
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
            PAIM
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
            startIcon={<HomeIcon />}
          >
            Home
          </Button>
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
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Tooltip title='Help'>
          <IconButton
            sx={{
              '& .MuiSvgIcon-root': {
                width: 28,
                height: 28
              }
            }}
          >
            <HelpOutlineIcon sx={{ color: 'white' }} />
          </IconButton>
        </Tooltip>
        <Tooltip title='Notification'>
          <IconButton
            sx={{
              '.MuiSvgIcon-root': {
                width: 30,
                height: 30
              }
            }}
          >
            <Badge badgeContent={2} color='error'>
              <NotificationsNoneIcon sx={{ color: 'white' }} />
            </Badge>
          </IconButton>
        </Tooltip>

        <Box sx={{ ml: 1.5,cursor:'pointer' }}>
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
            <MenuItem onClick={handleClose}>
              {' '}
              <AccountCircleIcon sx={{ marginRight: 1 }} /> Profile
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleClose}>
              <ManageAccountsIcon sx={{ marginRight: 1 }} />
              My account
            </MenuItem>
            <MenuItem onClick={handleClose}>
              <LogoutIcon sx={{ marginRight: 1 }} />
              Logout
            </MenuItem>
          </Menu>
        </Box>
      </Box>
    </Box>
  )
}

export default AppBar
