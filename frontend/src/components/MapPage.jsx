import { useEffect, useState, useMemo } from 'react'
import './MapPage.css'
import Map from './Map'
import AppBar from './AppBar/AppBar'
import BoardBar from './BoardBar/BoardBar'
import MapInfoBar from './MapInfoBar/MapInfoBar'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import ToolDial from './ToolDial/ToolDial'
import AppAlert from './AppAlert/AppAlert'
function MapPage() {
  // ── Constants ──────────────────────────────────────────────────────────────
  // Color palette keyed by incident nature (first word, lowercase)
  const NATURE_COLORS = {
    disturbance: '#e74c3c',
    assault: '#c0392b',
    theft: '#e67e22',
    burglary: '#d35400',
    traffic: '#3498db',
    suspicious: '#9b59b6',
    medical: '#1abc9c',
    fire: '#e74c3c',
    welfare: '#27ae60',
    domestic: '#c0392b',
    default: '#7f8c8d'
  }
  const LEE_COUNTY_CENTER = [26.56, -81.87]
  const API_BASE_URL = 'http://localhost:5001'
  // ── State ──────────────────────────────────────────────────────────────────
  const [daysAgo, setDaysAgo] = useState(3)
  const [allIncidents, setAllIncidents] = useState([])
  const [selectedNatures, setSelectedNatures] = useState([])
  const [locationMove, setLocationMove] = useState(null) //state to get lat, lng when user click on the item
  const [idPopup, setIdPopup] = useState(null) //state to get the id when user click on incident on the list
  // ── UI State ──────────────────────────────────────────────────────────────────
  const [addressSearch, setAddressSearch] = useState(false)
  const [isPulled, setIsPulled] = useState(false) //pull out the interactive list
  //This state is used for addresswithout location to trigger the function in Map
  const [noLocationMove, setNoLocationMove] = useState(null)
  //── Alert ───────────────────────────────────────────────────────────
  const [AlertContent, SetAlertContent] = useState({
    open: false,
    vertical: 'bottom',
    horizontal: 'center',
    severity: '',
    content: ''
  })
  // ── Data loading ───────────────────────────────────────────────────────────
  useEffect(() => {
    async function fetchData() {
      try {
        console.log('await....')
        const res = await fetch(
          `${API_BASE_URL}/api/v1/incidents?days=${daysAgo}&limit=500`
        )
        if (!res.ok) throw new Error(`HTTP ${res.status}`)

        const incidentList = await res.json()
        setAllIncidents(incidentList.incidents)
        const newNatures = [
          ...new Set(
            incidentList.incidents.map((inc) => inc.category || 'Unknown')
          )
        ].sort()
        setSelectedNatures(newNatures)
        //should have popup complete ***********************
        console.log('fetched successfully')
        //console.log(incidentList)

        //console.log(natures)
        //console.log(filtered)
      } catch (err) {
        console.error(err)
      }
    }
    fetchData()
  }, [daysAgo])
  // useEffect(() => {
  //   setSelectedNatures(natures)
  // }, [allIncidents, daysAgo])
  //derived value
  console.log('MapPage render')
  const filteredByDays = allIncidents
  const natures = [
    ...new Set(filteredByDays.map((inc) => inc.category || 'Unknown'))
  ].sort()
  const filteredList = handleNature(filteredByDays, selectedNatures)
  //console.log('filtered by days', filteredByDays)
  //console.log(selectedNatures, natures)
  //const filteredList = handleNature(filteredByDays, selectedNatures)
  const filteredListWithLocation = filteredList.filter(
    (incident) => incident.lat !== null && incident.lon !== null
  )
  const filteredListWithoutLocation = filteredList.filter(
    (incident) => incident.lat === null && incident.lon === null
  )

  //console.log('list with loc',filteredListWithLocation)
  //console.log('list without loc',filteredListWithoutLocation)
  //check

  // console.log('incident here: ', filteredList)
  // console.log('nature here: ', natures)
  // console.log('selectednature here: ', selectedNatures)
  const allType = selectedNatures.length === natures.length
  //console.log(allType)
  // function handleDays(incidents, daysAgo) {
  //   const cutoff = Date.now() - daysAgo * 24 * 60 * 60 * 1000

  //   return incidents.filter((inc) => {
  //     if (!inc.occurred_at) return false
  //     // Normalize to ISO 8601 for Safari: replace space, truncate to 3 decimal places
  //     const normalized = inc.occurred_at
  //       .replace(' ', 'T')
  //       .replace(/(\.\d{3})\d+/, '$1')
  //     return new Date(normalized).getTime() >= cutoff
  //   })
  // }
  function handleNature(incidentsByDays, selectedNatures) {
    return incidentsByDays.filter((inc) =>
      selectedNatures.includes(inc.category)
    )
  }
  function toggleNature(checkNature) {
    setSelectedNatures((nature) =>
      nature.includes(checkNature)
        ? nature.filter((item) => item !== checkNature)
        : [...nature, checkNature]
    )
  }
  function onNatureChange(nature) {
    toggleNature(nature)
  }
  //Get the lat lon when user click on the incident on the list (call back function)
  function getLocation(lat, lon) {
    setLocationMove([lat, lon])
  }
  //Get the id when user click on the incident on the list (callback function)
  function getIncidentID(id) {
    setIdPopup(id)
    //console.log(`popup id is ${idPopup}`)
  }

  //MUI func

  return (
    <Box
      sx={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        position: 'relative'
      }}
    >
      {/* App bar */}
      <AppBar />
      {/* Board bar */}
      <BoardBar
        filteredListWithLocation={filteredListWithLocation}
        filteredListWithoutLocation={filteredListWithoutLocation}
        getLocation={getLocation}
        getIncidentID={getIncidentID}
        setAddressSearch={setAddressSearch}
        addressSearch={addressSearch}
        setNoLocationMove={setNoLocationMove}
        setIsPulled={setIsPulled}
        incidentColors={NATURE_COLORS}
        SetAlertContent={SetAlertContent}
      />
      {console.log(noLocationMove)}

      <Box
        sx={{
          width: isPulled === true ? 'calc(100% - 400px)' : '100%',
          height: (theme) => theme.mapCustom.boardContentHeight,
          position: 'absolute',
          left: isPulled ? '400px' : '0px',
          transition: 'linear 0.3s',
          top: (theme) =>
            `calc( 100vh - ${theme.mapCustom.boardContentHeight})`,
          padding: '10px 15px 15px'
        }}
      >
        <Paper
          elevation={5}
          sx={{
            width: '100%',
            height: '100%',
            borderRadius: 2,
            overflow: 'hidden',
            position: 'relative'
          }}
        >
          <Box
            sx={{
              width: '100%',
              position: 'fixed',
              zIndex: 1000,
              top: (theme) =>
                `calc( ${theme.mapCustom.boardContentHeight} + 70px)`,
              left: '-15px'
            }}
          >
            <ToolDial />
          </Box>
          <Box
            sx={{
              width: '300px',
              position: 'fixed',
              zIndex: 1000,
              top: (theme) => `calc( ${theme.mapCustom.boardContentHeight} )`,
              left: '0px'
            }}
          >
            <AppAlert
              AlertContent={AlertContent}
              SetAlertContent={SetAlertContent}
            />
          </Box>

          <Box
            sx={{
              height: '50px',
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: 2,
              borderBottom: '1px solid',
              borderColor: 'divider'
            }}
          >
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                width: '200px',
                position: 'relative'
              }}
            >
              <Typography
                variant='span'
                sx={{ width: '400px', fontSize: '16px', fontWeight: 'bold' }}
              >
                Public Activity Interactive Map
              </Typography>
              <Typography
                variant='span'
                sx={{
                  width: '400px',
                  fontSize: '11px',
                  color: (theme) => theme.palette.grey[600]
                }}
              >
                Lee County Sheriff's Office — last 1,000 incidents (48hr delay)
              </Typography>
            </Box>
            {/* Map display bar */}
            <MapInfoBar
              daysAgo={daysAgo}
              setDaysAgo={setDaysAgo}
              selectedNatures={selectedNatures}
              setSelectedNatures={setSelectedNatures}
              filteredListWithLocation={filteredListWithLocation}
              allType={allType}
              natures={natures}
              onNatureChange={onNatureChange}
            />
          </Box>
          <Box
            sx={{
              height: 'calc(100% - 50px)',
              width: isPulled === true ? 'calc(100% + 400px)' : '100%',
              transform: isPulled ? 'translateX(-200px)' : 'translateX(0)',
              transition: 'linear 0.3s'
            }}
          >
            <Map
              finalList={filteredListWithLocation}
              countyCenter={LEE_COUNTY_CENTER}
              locationMove={locationMove}
              idPopup={idPopup}
              addressSearch={addressSearch}
              setAddressSearch={setAddressSearch}
              noLocationMove={noLocationMove}
              SetAlertContent={SetAlertContent}
            />
          </Box>
        </Paper>
      </Box>
    </Box>
  )
}

export default MapPage
