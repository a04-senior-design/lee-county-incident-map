import { useEffect, useState, useMemo } from 'react'
import './MapPage.css'
import Map from './Map'
import AppBar from './AppBar/AppBar'
import BoardBar from './BoardBar/BoardBar'
import MapInfoBar from './MapInfoBar/MapInfoBar'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import AppAlert from './AppAlert/AppAlert'
import dayjs from 'dayjs'
import { useAuth } from '../Context/AuthContext'

const today = dayjs()

function cleanDuplicateId(incidentList) {
  const bucket = new Set()
  const newList = incidentList.filter((inc) => {
    if (bucket.has(inc.source_incident_id)) return false
    bucket.add(inc.source_incident_id)
    return true
  })
  return newList
}

const LEE_COUNTY_CENTER = [26.56, -81.87]
function MapPage() {
  const { user } = useAuth()

  // ── Constants ──────────────────────────────────────────────────────────────
  // Color palette keyed by incident nature (first word, lowercase)
  const CATEGORY_COLORS = {
  VIOLENT: '#c0392b',
  FIREARM: '#7b241c',
  SEX_OFFENSE: '#8e44ad',
  BURGLARY: '#d35400',
  THEFT: '#e67e22',
  VEHICLE: '#f1c40f',
  FRAUD: '#16a085',
  DRUGS: '#27ae60',
  HARASSMENT: '#e84393',
  DISTURBANCE: '#9fc513', // muted on purpose, it's 158k incidents
  TRAFFIC: '#3498db',
  DEATH: '#2c3e50',
  ANIMAL: '#8d6e63',
  HAZARD: '#00bcd4',
  OTHER: '#7f8c8d'
}
  const database = import.meta.env.VITE_API_BASE_URL
  // ── State ──────────────────────────────────────────────────────────────────
  const [daysAgo, setDaysAgo] = useState(3)
  const [allIncidents, setAllIncidents] = useState([])
  const [selectedNatures, setSelectedNatures] = useState([])
  const [locationMove, setLocationMove] = useState(null) //state to get lat, lng when user click on the item
  const [idPopup, setIdPopup] = useState(null) //state to get the id when user click on incident on the list
  const [dateRange, setDateRange] = useState([
    today.subtract(7, 'day').format('YYYY-MM-DD'),
    today.format('YYYY-MM-DD')
  ])
  const [start_date, end_date] = dateRange
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
  //── Overlay ───────────────────────────────────────────────────────────
  const [isLoading, setIsLoading] = useState(false)
  //── Route safety ───────────────────────────────────────────────────────────
  const [routeOn, setRouteOn] = useState(false)
  useEffect(() => {
    if (user) {
      SetAlertContent({
        open: true,
        vertical: 'bottom',
        horizontal: 'center',
        severity: 'success',
        content: 'User login successfully'
      })
    } else {
      SetAlertContent({
        open: true,
        vertical: 'bottom',
        horizontal: 'center',
        severity: 'warning',
        content: 'log in as guest'
      })
    }
  }, [user])
  //── Analysis mode ───────────────────────────────────────────────────────────
  const [analysisOn, setAnalysisOn] = useState(false)

  const [selectedId, setSelectedId] = useState(null)
  useEffect(() => {
    const [fromDay, toDay] = dateRange
    if (!fromDay || !toDay) return

    const controller = new AbortController()

    async function fetchAll() {
      try {
        let all = []
        let cursor = null
        let count = 0
        setIsLoading(true)
        do {
          const params = new URLSearchParams({
            from: fromDay,
            to: toDay,
            limit: '500'
          })
          if (cursor) params.set('cursor', cursor) // confirm this param name

          const res = await fetch(`${database}/incidents?${params}`, {
            signal: controller.signal
          })
          if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${await res.text()}`)
          }

          const page = await res.json()
          all = all.concat(page.incidents)
          cursor = page.next_cursor
          count++
        } while (count < 20)
        setIsLoading(false)
        setAllIncidents(all)
        setSelectedNatures(
          [...new Set(all.map((inc) => inc.category || 'Unknown'))].sort()
        )
      } catch (err) {
        if (err.name !== 'AbortError') console.error(err)
      }
    }

    fetchAll()
    return () => controller.abort()
  }, [dateRange])
  // useEffect(() => {
  //   const [fromDay, toDay] = dateRange
  //   if (!fromDay || !toDay) return

  //   async function fetchData() {
  //     try {
  //       console.log('fromDay:', fromDay)
  //       console.log('toDay:', toDay)
  //       console.log('await....')
  //       const url = `${database}/incidents?from=${fromDay}&to=${toDay}&limit=500`
  //       //console.log('API URL:', url)
  //       const res = await fetch(url)
  //       if (!res.ok) {
  //         const errorText = await res.text()
  //         throw new Error(`HTTP ${res.status}: ${errorText}`)
  //       }

  //       const incidentList = await res.json()

  //       console.log('incidentList =', incidentList)

  //       setAllIncidents(incidentList.incidents)

  //       const newNatures = [
  //         ...new Set(
  //           incidentList.incidents.map((inc) => inc.category || 'Unknown')
  //         )
  //       ].sort()

  //       setSelectedNatures(newNatures)

  //       console.log('fetched successfully')
  //     } catch (err) {
  //       console.error(err)
  //     }
  //   }

  //   fetchData()
  // }, [dateRange])

  // useEffect(() => {
  //   setSelectedNatures(natures)
  // }, [allIncidents, daysAgo])
  //derived value
  //console.log('MapPage render')
  const filteredByDays = allIncidents
  const natures = [
    ...new Set(filteredByDays.map((inc) => inc.category || 'Unknown'))
  ].sort()
  const filteredList = useMemo(
    () => handleNature(filteredByDays, selectedNatures),
    [filteredByDays, selectedNatures]
  )
  //console.log('filtered by days', filteredByDays)
  //console.log(selectedNatures, natures)
  //const filteredList = handleNature(filteredByDays, selectedNatures)
  const filteredListWithLocation = useMemo(
    () =>
      cleanDuplicateId(
        filteredList.filter((i) => i.lat != null && i.lon != null)
      ),
    [filteredList]
  )
  const filteredListWithoutLocation = useMemo(
    () =>
      cleanDuplicateId(
        filteredList.filter((i) => i.lat == null || i.lon == null)
      ),
    [filteredList]
  )
  console.log(filteredListWithLocation)
  //console.log('list with loc', filteredListWithLocation)
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
        isPulled={isPulled}
        setIsPulled={setIsPulled}
        incidentColors={CATEGORY_COLORS}
        SetAlertContent={SetAlertContent}
        analysisOn={analysisOn}
        setAnalysisOn={setAnalysisOn}
        dateRange={dateRange}
        setIdPopup={setIdPopup}
        setSelectedId={setSelectedId}
        routeOn = {routeOn}
        setRouteOn = {setRouteOn}
        isLoading = {isLoading}
      />

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
          {/* <Box
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
          </Box> */}
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
                  fontWeight: 600,
                  color: (theme) => theme.palette.grey[400]
                }}
              >
                Lee County Sheriff's Office
              </Typography>
            </Box>
            {/* Map display bar */}
            <MapInfoBar
              daysAgo={daysAgo}
              setDaysAgo={setDaysAgo}
              selectedNatures={selectedNatures}
              setSelectedNatures={setSelectedNatures}
              filteredListWithLocation={filteredListWithLocation}
              filteredListWithoutLocation={filteredListWithoutLocation}
              allType={allType}
              natures={natures}
              onNatureChange={onNatureChange}
              dateRange={dateRange}
              setDateRange={setDateRange}
            />
          </Box>
          <Box
            sx={{
              height: 'calc(100% - 50px)',
              width: isPulled === true ? 'calc(100% + 400px)' : '100%',
              transform: `translateX(${isPulled ? '-200px' : '0'})`,
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
              analysisOn={analysisOn}
              selectedId={selectedId}
              setSelectedId={setSelectedId}
              start_date={start_date}
              end_date={end_date}
              isLoading={isLoading}
              setIsLoading={setIsLoading}
              routeOn={routeOn}
              setRouteOn={setRouteOn}
              incidentColors = {CATEGORY_COLORS}
            />
          </Box>
        </Paper>
      </Box>
    </Box>
  )
}

export default MapPage
