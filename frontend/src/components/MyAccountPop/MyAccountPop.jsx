import React, { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import { useAuth } from '../../Context/AuthContext'
import Typography from '@mui/material/Typography'
import Card from '@mui/material/Card'
import CardMedia from '@mui/material/CardMedia'
import CardContent from '@mui/material/CardContent'
import CardActions from '@mui/material/CardActions'
import ModeSelect from '../ModeSelect/ModeSelect'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
const url = import.meta.env.VITE_API_BASE_URL

function MyAccountPop({ accountPop, setAccountPop, CATEGORY_COLORS }) {
  const [notiList, setNotiList] = useState()
  const { user, token } = useAuth()
  const pickColor = (category) => {
    const key = category || ''
    for (const color in CATEGORY_COLORS) {
      if (key.includes(color)) return CATEGORY_COLORS[color]
    }

    return CATEGORY_COLORS.default
  }
  useEffect(() => {
    if (!accountPop || !token) return
    const fetchNotiList = async () => {
      try {
        const res = await fetch(`${url}/users/me/areas`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (!res.ok) throw new Error('area list has problem')
        const data = await res.json()
        console.log(data)
        setNotiList(data.areas)
      } catch (error) {
        console.log(error.message)
      }
    }
    fetchNotiList()
  }, [accountPop, token])
  const handleDelete = async (id) => {
    try {
      const res = await fetch(`${url}/users/me/areas/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('area delete has problem')
      setNotiList((prev) => prev.filter((area) => area.id !== id))
    } catch (error) {
      console.log(error.message)
    }
  }
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(255,255,255,0.8)',
        zIndex: 5000,
        position: 'absolute',
        alignItems: 'center',
        justifyContent: 'center',
        display: accountPop ? 'flex' : 'none',
        flexDirection: 'column'
      }}
    >
      <Box
        sx={[
          {
            width: 'clamp(380px, 40vw, 600px)',
            background: 'white',
            borderRadius: '16px',
            p: 1,
            border: '2px solid',
            borderColor: (theme) => theme.palette.primary.main
          },
          (theme) =>
            theme.applyStyles('light', {
              backgroundColor: '#ffffff'
            }),
          (theme) =>
            theme.applyStyles('dark', {
              backgroundColor: 'rgba(1, 1, 26, 0.92)'
            })
        ]}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <Button
            onClick={() => {
              setAccountPop(false)
            }}
          >
            {' '}
            Close
          </Button>
          <ModeSelect />
        </Box>

        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            gap: 2,
            p: 3
          }}
        >
          <Box>
            <Typography variant='span'> Welcome</Typography>
            <Typography
              sx={{ fontSize: '24px', fontWeight: 600 }}
              color='primary'
              variant='span'
            >
              {' '}
              {user?.name}
            </Typography>
          </Box>
          <Box>
            <Typography variant='span'> Email: </Typography>
            <Typography
              sx={{ fontSize: '24px', fontWeight: 600 }}
              color='primary'
              variant='span'
            >
              {' '}
              {user?.email}
            </Typography>
          </Box>
          <Typography variant='h6'> Notification list: </Typography>
          <Box sx={{ width: '100%', height: '500px', overflow: 'auto', p: 1 }}>
            {notiList?.map((item) => (
              <Card
                elevation={3}
                key={item.id}
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
                      justifyContent: 'space-between'
                    }}
                  >
                    <Typography
                      gutterBottom
                      variant='h5'
                      component='div'
                      sx={{
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden'
                      }}
                    >
                      {item.name}
                    </Typography>
                    <Button
                      onClick={() => {
                        if (window.confirm(`Delete "${item.name}"?`)) {
                          handleDelete(item.id)
                        }
                      }}
                    >
                      <DeleteOutlineIcon color='error' />
                    </Button>
                  </Box>

                  {/* <Typography
                    gutterBottom
                    variant='body2'
                    component='div'
                    sx={{
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden'
                    }}
                  >
                    address here
                  </Typography> */}
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between'
                    }}
                  >
                    <Typography
                      variant='h7'
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
                      {`Radius: ${item.radius_mi} miles`}
                    </Typography>
                    <Typography
                      variant='body2'
                      sx={{ color: 'text.secondary' }}
                    >
                      {`${item.created_at.split('T')[0]}`}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 2, mt: '20px' }}>
                    <Typography
                      variant='span'
                      sx={[
                        {
                          fontWeight: 500,
                          fontSize: '14px'
                        }
                      ]}
                    >
                      {`Categories:  `}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                      {item.categories.map((c) => (
                        <Typography
                          variant='h7'
                          sx={[
                            {
                              fontWeight: 700,
                              color: pickColor(c)
                            }
                          ]}
                        >
                          {c}
                        </Typography>
                      ))}
                    </Box>
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
            ))}
          </Box>
        </Box>
      </Box>
    </Box>
  )
}

export default MyAccountPop
