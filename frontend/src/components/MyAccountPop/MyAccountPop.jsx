import { useEffect,  useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import { useAuth } from '../../Context/AuthContext'
import Typography from '@mui/material/Typography'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import ModeSelect from '../ModeSelect/ModeSelect'
import BorderColorIcon from '@mui/icons-material/BorderColor'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import EditForm from './EditForm/EditForm'
const url = import.meta.env.VITE_API_BASE_URL

function MyAccountPop({
  accountPop,
  setAccountPop,
  CATEGORY_COLORS,
  searching,
  addressType,
  addressList,
  checkBound,
  setAddressList,
  setAddressType,
  showAlert,
  addressSearch,
  setAddressSearch
}) {
  const [notiList, setNotiList] = useState()
  const { user, token, refreshToken } = useAuth()
  const [editCard, setEditCard] = useState(false)
  const [editCardContent, setEditCardContent] = useState(false)
  const [alertTrigger, setAlertTrigger] = useState(0) //just set a state to trigger the noti list render useeffect

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
        const send = (token) =>
          fetch(`${url}/users/me/areas`, {
            headers: { Authorization: `Bearer ${token}` }
          })

        let res = await send(token)

        if (res.status === 401) {
          const newToken = await refreshToken()
          if (newToken) res = await send(newToken)
        }
        if (!res.ok) throw new Error('area list has problem')
        const data = await res.json()
        console.log(data)
        setNotiList(data.areas)
      } catch (error) {
        console.log(error.message)
      }
    }
    fetchNotiList()
  }, [accountPop, token, editCard, alertTrigger])
  const handleDelete = async (id) => {
    try {
      const send = (token) =>
        fetch(`${url}/users/me/areas/${id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` }
        })
      let res = await send(token)
      if (res.status === 401) {
        const newToken = await refreshToken()
        if (newToken) res = await send(newToken)
      }
      if (!res.ok) throw new Error('area delete has problem')
      setNotiList((prev) => prev.filter((area) => area.id !== id))
    } catch (error) {
      console.log(error.message)
    }
  }
  const editNoti = async (id, alert) => {
    try {
      console.log('alert editing... ', alert)
      const send = (token) =>
        fetch(`${url}/users/me/areas/${id}`, {
          method: 'PATCH',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            alerts_enabled: !alert
          })
        })
      let res = await send(token)
      if (res.status === 401) {
        const newToken = await refreshToken()
        if (newToken) res = await send(newToken)
      }
      if (!res.ok) throw new Error('alert noti has problem')
      setAlertTrigger((e) => e + 1)
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
                      color='primary'
                      sx={{
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        fontWeight: 600
                      }}
                    >
                      {item.name.toUpperCase()}
                    </Typography>
                    <Box>
                      <Button
                        variant=''
                        onClick={() => {
                          setEditCard(true)
                          setEditCardContent(item)
                        }}
                      >
                        <BorderColorIcon color='primary' />
                      </Button>
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
                  </Box>

                  <Typography
                    variant='h5'
                    sx={{
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden'
                    }}
                  >
                    {item.address}
                  </Typography>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',

                      mt: 1
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

                  <Button
                    sx={{ mt: '10px' }}
                    onClick={() => editNoti(item.id, item.alerts_enabled)}
                    color={item.alerts_enabled ? 'success' : 'error'}
                    variant='outlined'
                  >
                    Alert Enable: {item.alerts_enabled ? 'On' : 'Off'}
                  </Button>
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
      {editCard && (
        <Box sx={{ position: 'absolute', zIndex: 10000, top: '30%' }}>
          <EditForm
            item={editCardContent}
            searching={searching}
            addressType={addressType}
            addressList={addressList}
            checkBound={checkBound}
            setAddressList={setAddressList}
            setAddressType={setAddressType}
            showAlert={showAlert}
            addressSearch={addressSearch}
            setAddressSearch={setAddressSearch}
            editCard={editCard}
            setEditCard={setEditCard}
          />
        </Box>
      )}
    </Box>
  )
}

export default MyAccountPop
