import { useEffect, useState, useRef, useCallback } from 'react'
import Tooltip from '@mui/material/Tooltip'
import IconButton from '@mui/material/IconButton'
import Badge from '@mui/material/Badge'
import Popover from '@mui/material/Popover'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import ListItemText from '@mui/material/ListItemText'
import Typography from '@mui/material/Typography'
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone'
import { useAuth } from '../../Context/AuthContext'
import NotiPopup from './NotiPopup/NotiPopup'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
const url = import.meta.env.VITE_API_BASE_URL
const timeSend = 3 * 60 * 1000

function AppNoti({ CATEGORY_COLORS }) {
  const { token } = useAuth()
  const [alerts, setAlerts] = useState([])
  const [cursor, setCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)
  const [anchorEl, setAnchorEl] = useState(null)
  const openRef = useRef(false)
  const pickColor = (category) => {
    const key = category || ''
    for (const color in CATEGORY_COLORS) {
      if (key.includes(color)) return CATEGORY_COLORS[color]
    }

    return CATEGORY_COLORS.default
  }

  const fetchNoti = useCallback(async () => {
    if (openRef.current) return // don't replace the list the user is reading
    try {
      const res = await fetch(`${url}/users/me/alerts`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('noti has problem')
      const data = await res.json()
      setAlerts(data.alerts ?? [])
      setCursor(data.cursor ?? null)
      setHasMore(Boolean(data.has_more))
    } catch (error) {
      console.log(error.message)
    }
  }, [token])

  useEffect(() => {
    if (!token) return
    fetchNoti()
    const id = setInterval(fetchNoti, timeSend)
    return () => clearInterval(id)
  }, [token, fetchNoti])
  const markSeen = async (c) => {
    if (!c) return
    try {
      const res = await fetch(`${url}/users/me/alerts/seen`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ cursor: c })
      })
      if (!res.ok) throw new Error('mark seen has problem')
      // the success response is 204 with no body, so don't call res.json()
    } catch (error) {
      console.log(error.message)
    }
  }
  const handleOpen = (e) => {
    setAnchorEl(e.currentTarget)
    openRef.current = true
    markSeen(cursor)
  }
  const handleClose = () => {
    openRef.current = false
    setAnchorEl(null)
    setAlerts([])
    setCursor(null)
    const more = hasMore
    setHasMore(false)
    if (more) fetchNoti() // the backend returns at most 100 per call, so load the rest
  }
  return (
    <>
      <Tooltip title='Notification'>
        <IconButton
          onClick={handleOpen}
          sx={{ '.MuiSvgIcon-root': { width: 30, height: 30 } }}
        >
          <Badge
            badgeContent={
              anchorEl ? 0 : hasMore ? `${alerts.length}+` : alerts.length
            }
            color='error'
          >
            <NotificationsNoneIcon sx={{ color: 'white' }} />
          </Badge>
        </IconButton>
      </Tooltip>

      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={() => handleClose()}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <List sx={{ width: 350, maxHeight: 400, overflow: 'auto', p: 1 }}>
          {alerts.length === 0 ? (
            <Typography sx={{ p: 2 }} color='text.secondary'>
              No new alerts
            </Typography>
          ) : (
            [...alerts].reverse().map((alert, index) => (
              <Card
                elevation={3}
                key={index}
                sx={[
                  {
                    '&:hover': {
                      transform: 'scale(1.02)'
                    },
                    width: '95%',
                    flexShrink: 0,
                    mt: '10px',
                    transition: '0.3s'
                  },
                  (theme) =>
                    theme.applyStyles('light', {
                      backgroundColor: '#ffffff'
                    }),
                  (theme) =>
                    theme.applyStyles('dark', {
                      backgroundColor: 'rgba(23, 23, 85, 0.92)'
                    })
                ]}
              >
                <CardContent sx={{ padding: '16px 16px 5px' }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2
                    }}
                  >
                    {alert.areas?.map((area) => (
                      <Typography
                        key={area}
                        gutterBottom
                        variant='h5'
                        component='div'
                        sx={{
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden'
                        }}
                      >
                        {area}
                      </Typography>
                    ))}
                  </Box>
                  <Box sx={{}}>
                    <Typography
                      sx={[
                        {
                          fontWeight: 700,
                          color: (theme) => theme.palette.warning.dark
                        },
                        (theme) =>
                          theme.applyStyles('dark', {
                            color: 'warning.main'
                          })
                      ]}
                    >
                      {`Address: ${alert.address}`}
                    </Typography>
                    <Typography
                      variant='body2'
                      sx={{ color: 'text.secondary' }}
                    >
                      {`${alert.occurred_at.split('T')[0]} / ${alert.occurred_at.split('T')[1].slice(0, 8)}`}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <Typography
                      sx={[
                        {
                          fontWeight: 500,
                          fontSize: '14px'
                        }
                      ]}
                    >
                      {`Categories:  `}
                    </Typography>

                    <Typography
                      sx={[
                        {
                          fontWeight: 700,
                          color: pickColor(alert.category)
                        }
                      ]}
                    >
                      {alert.category}
                    </Typography>
                  </Box>
                </CardContent>
                {/* <CardActions>
                  <Button size='small'>Share</Button>
                  <Button
                    //   endIcon={<ArrowOutwardIcon sx={{}} />}
                    size='small'
                    onClick={() => {}}
                  >
                    'Go to Map'
                  </Button>
                </CardActions> */}
              </Card>
            ))
          )}
        </List>
      </Popover>
    </>
  )
}

export default AppNoti
