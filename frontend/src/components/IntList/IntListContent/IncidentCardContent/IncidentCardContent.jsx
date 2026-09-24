import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardActions from '@mui/material/CardActions'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import ArrowOutwardIcon from '@mui/icons-material/ArrowOutward'
import CardMedia from '@mui/material/CardMedia'
import Box from '@mui/material/Box'
import { useState } from 'react'
function IncidentCardContent({
  incidentList,
  getLocation,
  getIncidentID,
  latlon,
  setNoLocationMove,
  incidentColors
}) {
  const [targetCard, setTargetCard] = useState(null)
  const pickColor = (incident) => {
    const key = incident.nature.toLowerCase()
    for (const color in incidentColors) {
      if (key.includes(color)) return incidentColors[color]
    }

    return incidentColors.default
  }
  const selectCard = (key) => {
    setTargetCard(key)
  }
  return (
    <>
      {incidentList?.map((incident) => (
        <Card
          elevation={2}
          key={incident.source_incident_id}
          sx={[
            {
              width: '95%',
              height: '180px',
              flexShrink: 0,
              transform:
                targetCard === incident.id
                  ? 'translateX(10px) scale(1.04)'
                  : 'none',
              transition: '0.3s'
            },
            (theme) =>
              theme.applyStyles('light', {
                backgroundColor: '#fafafa'
              })
          ]}
          onClick={() => selectCard(incident.id)}
        >
          <CardMedia
            sx={{ height: 20, bgcolor: () => pickColor(incident) }}
            title='incident color'
          />
          <CardContent sx={{ padding: '16px 16px 5px' }}>
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
              {incident.address}
            </Typography>
            <Typography
              gutterBottom
              variant='body2'
              component='div'
              sx={{
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                overflow: 'hidden'
              }}
            >
              {incident.city}
            </Typography>
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
                {incident.nature}
              </Typography>
              <Typography variant='body2' sx={{ color: 'text.secondary' }}>
                {`${incident.occurred_at.split('T')[0]}`}
              </Typography>
            </Box>
          </CardContent>
          <CardActions>
            <Button size='small'>Share</Button>
            <Button
              endIcon={<ArrowOutwardIcon sx={{}} />}
              size='small'
              onClick={() => {
                if (latlon === 1) {
                  getLocation(incident.lat, incident.lon)
                  getIncidentID(incident.source_incident_id)
                } else {
                  setNoLocationMove({
                    address: incident.address,
                    trigger: Date.now()
                  })
                }
              }}
            >
              {latlon === 1 ? 'Go to Map' : 'Search on map'}
            </Button>
          </CardActions>
        </Card>
      ))}
    </>
  )
}
//.split(' ')[0].split('-').reverse().join('-')

export default IncidentCardContent
