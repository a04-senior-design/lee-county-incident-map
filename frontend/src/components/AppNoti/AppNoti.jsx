import React, { useEffect, useState } from 'react'
import Tooltip from '@mui/material/Tooltip'
import IconButton from '@mui/material/IconButton'
import Badge from '@mui/material/Badge'
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone'

import { useAuth } from '../../Context/AuthContext'
const url = import.meta.env.VITE_API_BASE_URL
const timeSend = 5 * 60 * 1000

function AppNoti() {
  const {token} = useAuth()
  const [notiNumbers, setNotiNumber] = useState(0)

  const fetchNoti = async () => {
    try {
      const res = await fetch(`${url}/users/me/alerts`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('noti has problem')
      const data = await res.json()
      console.log(data)
      setNotiNumber((prev) => prev + 1)
    } catch (error) {
      console.log(error.message)
    }
  }
  useEffect(() => {
    fetchNoti()
  }, [])
  useEffect(() => {
    const notification = setInterval(async () => {
      fetchNoti()
    }, timeSend)
    return () => clearInterval(notification)
  }, [])
  return (
    <Tooltip title='Notification'>
      <IconButton
        sx={{
          '.MuiSvgIcon-root': {
            width: 30,
            height: 30
          }
        }}
      >
        <Badge badgeContent={notiNumbers} color='error'>
          <NotificationsNoneIcon sx={{ color: 'white' }} />
        </Badge>
      </IconButton>
    </Tooltip>
  )
}

export default AppNoti
