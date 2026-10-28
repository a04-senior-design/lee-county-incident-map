import Box from '@mui/material/Box'
import { useState } from 'react'
import Typography from '@mui/material/Typography'
import TextField from '@mui/material/TextField'
import IncidentCardContent from './IncidentCardContent/IncidentCardContent'
function IntListContent({
  incidentList,
  getLocation,
  getIncidentID,
  latlon,
  setNoLocationMove,
  incidentColors
}) {
  const [searchResult, setSearchResult] = useState('')
  const filterIncident = (e) => {
    setSearchResult(e.target.value)
  }
  const resultList = incidentList.filter((incident) =>
    incident.address.includes(searchResult.toUpperCase())
  )
  const incidentCount = resultList.length
  return (
    <Box sx={{}}>
      <Box
        sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}
      >
        <TextField
          autoComplete='off'
          type='search'
          id='filterList'
          label='Filter Address'
          variant='outlined'
          size='small'
          onChange={filterIncident}
          value={searchResult}
          sx={[
            { width: '250px' },
            (theme) =>
              theme.applyStyles('light', {
                borderColor: theme.palette.grey[900]
              }),
            (theme) =>
              theme.applyStyles('dark', {
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#fff'
                }
              })
          ]}
        />
        <Typography sx={{ fontWeight: 500 }}>
          {searchResult.length !== 0
            ? `${incidentCount} incidents`
            : `${incidentList.length} incidents`}
        </Typography>
      </Box>
      <Box
        sx={(theme) => ({
          marginTop: 2,
          height: {
            xs: '200px',
            md: theme.mapCustom.listCardHeight
          },
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          px: 1,
          paddingTop: 1
        })}
      >
        <IncidentCardContent
          incidentList={resultList}
          getLocation={getLocation}
          getIncidentID={getIncidentID}
          latlon={latlon}
          setNoLocationMove={setNoLocationMove}
          incidentColors={incidentColors}
        />
      </Box>
    </Box>
  )
}

export default IntListContent
