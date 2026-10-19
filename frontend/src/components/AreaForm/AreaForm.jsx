import TextField from '@mui/material/TextField'
import FormControl from '@mui/material/FormControl'
import Slider from '@mui/material/Slider'
import Radio from '@mui/material/Radio'
import Box from '@mui/material/Box'
import FormLabel from '@mui/material/FormLabel'
import RadioGroup from '@mui/material/RadioGroup'
import FormControlLabel from '@mui/material/FormControlLabel'
import Typography from '@mui/material/Typography'
import Divider from '@mui/material/Divider'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import Button from '@mui/material/Button'
import { useState } from 'react'
import { useAuth } from '../../Context/AuthContext'
const url = import.meta.env.VITE_API_BASE_URL
function AreaForm({
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
  const { token } = useAuth()
  const [noti, setNoti] = useState({
    name: '',
    lat: null,
    lon: null,
    radius_mi: 5
  })
  const handleChange = (param, value) => {
    setNoti((prev) => ({
      ...prev,
      [param]: value
    }))
  }
  const handleSubmit = async (e) => {
    e.preventDefault()
    console.log(noti)
    if (!noti.lat || !noti.lon) return
    try {
      const res = await fetch(`${url}/users/me/areas`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: noti.name,
          lat: noti.lat,
          lon: noti.lon,
          radius_mi: noti.radius_mi,
          categories: ['BURGLARY', 'THEFT'],
          alerts_enabled: true
        })
      })
      if (!res.ok) throw new Error('noti form has problem')
      showAlert('success', 'area saved successfully')
      setNoti({
        name: '',
        lat: null,
        lon: null,
        radius_mi: 5
      })
      setAddressType('')
    } catch (error) {
      console.log(error.message)
    }
  }
  return (
    <form action='submit' onSubmit={handleSubmit}>
      <Box
        sx={[
          {
            height: '400px',
            background: 'white',
            p: 2,
            borderRadius: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2
          },
          (theme) =>
            theme.applyStyles('dark', {
              backgroundColor: 'rgba(1, 1, 26, 0.92)'
            })
        ]}
      >
        <Box>Notification Form</Box>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 2
          }}
        >
          {' '}
          <TextField
            autoComplete='off'
            value={noti.name}
            id='filled-basic'
            label='Name your address'
            variant='filled'
            onChange={(e) => {
              handleChange('name', e.target.value)
            }}
          />
          <Box sx={{ position: 'relative' }}>
            <TextField
              autoComplete='off'
              id='filterList'
              type='text'
              label='Enter address'
              variant='filled'
              onChange={searching}
              value={addressType}
              sx={[
                {
                  width: '350px'
                }
              ]}
            />
            <List
              sx={{ p: '3px 0', position: 'absolute', top: '', zIndex: 1000 }}
            >
              {addressType.length !== 0 &&
                addressList?.map((address, index) => (
                  <>
                    <ListItem
                      key={index}
                      sx={{
                        backgroundColor: 'white',
                        width: '350px',
                        p: 0
                      }}
                    >
                      <ListItemButton
                        onClick={() => {
                          setAddressType(address.place_name)
                          setAddressList(null)
                          checkBound([address.center])
                          handleChange('lat', address.center[1])
                          handleChange('lon', address.center[0])
                        }}
                      >
                        <ListItemText
                          primary={address.place_name}
                          sx={{
                            color: 'black'
                          }}
                          slotProps={{
                            textOverflow: 'ellipsis',
                            overflow: 'hidden'
                          }}
                        />
                      </ListItemButton>
                    </ListItem>
                  </>
                ))}
            </List>
          </Box>
        </Box>
        <Box>
          <FormLabel id='radio-noti-time-group-label'>Time</FormLabel>
          <RadioGroup
            row
            aria-labelledby='demo-radio-buttons-group-label'
            defaultValue='weekly'
            name='radio-buttons-group'
          >
            <FormControlLabel
              value='weekly'
              control={<Radio />}
              label='weekly'
            />
            <FormControlLabel
              value='bi-weekly'
              control={<Radio />}
              label='bi-weekly'
            />
            <FormControlLabel
              value='monthly'
              control={<Radio />}
              label='monthly'
            />
          </RadioGroup>
        </Box>
        <Box>
          <FormLabel id='radio-noti-distance-group-label'>
            Distance (miles)
          </FormLabel>
          <Box
            sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '80%' }}
          >
            <Typography sx={{ fontSize: '20px', fontWeight: 500 }} color='text'>
              {' '}
              2
            </Typography>
            <Slider
              valueLabelDisplay='auto'
              aria-label='Default'
              id={`slider-noti`}
              min={2}
              max={10}
              step={0.5}
              value={noti.radius_mi}
              color='success'
              onChange={(_, value) => {
                handleChange('radius_mi', value)
              }}
            />

            <Typography sx={{ fontSize: '20px', fontWeight: 500 }} color='text'>
              {' '}
              10
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 4 }}>
          <Button variant='contained' color='error' onClick={() => setAddressSearch(!addressSearch)}>
            Cancel
          </Button>
          <Button variant='contained' type='submit'>
            Save
          </Button>
        </Box>
      </Box>
    </form>
  )
}

export default AreaForm
