import ModeSelect from '../ModeSelect/ModeSelect'
import Box from '@mui/material/Box'
import IntList from '../IntList/IntList'
import Button from '@mui/material/Button'
import TravelExploreIcon from '@mui/icons-material/TravelExplore'
import TextSnippetIcon from '@mui/icons-material/TextSnippet'
import AssessmentIcon from '@mui/icons-material/Assessment'
import { useState } from 'react'
import AnimationIcon from '@mui/icons-material/Animation'
import { useAuth } from '../../Context/AuthContext'
import RouteIcon from '@mui/icons-material/Route'
import AddAlertIcon from '@mui/icons-material/AddAlert';
function BoardBar({
  filteredListWithLocation,
  filteredListWithoutLocation,
  getLocation,
  getIncidentID,
  setAddressSearch,
  addressSearch,
  setNoLocationMove,
  isPulled,
  setIsPulled,
  incidentColors,
  analysisOn,
  setAnalysisOn,
  dateRange,
  routeOn,
  setRouteOn,
  setSelectedId,
  isLoading,
  accountPop
}) {
  // const [activeBtn, setActiveBtn] = useState({
  //   search: false,
  //   dbscan: false,
  //   heatMap: false,
  //   animation: false
  // })
  const { user, token } = useAuth()
  const [activeBtn, setActiveBtn] = useState(null)
  const [reportBtn, setReportBtn] = useState(false)
  const handleActive = (e) => {
    const value = e.currentTarget.value
    setActiveBtn(value)
    console.log('value ', value)
  }
  const API_URL = import.meta.env.VITE_API_BASE_URL
  const [reportLoading, setReportLoading] = useState(false)

  const handleReport = async () => {
    setReportLoading(true)
    const [from, to] = dateRange
    const incidents = filteredListWithLocation.map((i) => ({
      nature: i.category,
      city: i.city, // still need to confirm this field name
      lat: i.lat,
      lng: i.lon,
      occuredDate: i.occurred_at
    }))

    setReportLoading(true)
    try {
      const res = await fetch(`${API_URL}/reports?from=${from}&to=${to}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `Server error ${res.status}`)
      }
      const blob = await res.blob()
      console.log('res here', res)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `lee-county-report-${from}_to_${to}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert(`Report generation failed: ${err.message}`)
    } finally {
      setReportLoading(false)
      setReportBtn(false)
    }
  }
  return (
    <Box
      sx={[
        {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          height: (theme) => theme.mapCustom.boardBarHeight,
          bgcolor: 'primary.main'
        },
        (theme) =>
          theme.applyStyles('dark', {
            backgroundColor: 'rgba(20, 20, 41, 0.92)'
          }),
        (theme) =>
          theme.applyStyles('light', {
            backgroundColor: 'rgba(255, 255, 255, 0.92)'
          })
      ]}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2
        }}
      >
        <IntList
          listWithLocation={filteredListWithLocation}
          listWithoutLocation={filteredListWithoutLocation}
          getLocation={getLocation}
          getIncidentID={getIncidentID}
          setNoLocationMove={setNoLocationMove}
          isPulled={isPulled}
          setIsPulled={setIsPulled}
          incidentColors={incidentColors}
          analysisOn={analysisOn}
          routeOn={routeOn}
          setSelectedId = {setSelectedId}
        />
        <Button
          variant={addressSearch ? 'contained' : 'text'}
          color={addressSearch ? 'success' : 'primary'}
          sx={[
            (theme) =>
              theme.applyStyles('dark', {
                color: 'rgba(255, 255, 255, 0.92)'
              }),
            { padding: '8px 16px' }
          ]}
          startIcon={<AddAlertIcon />}
          onClick={() => {
            setAddressSearch(!addressSearch)
            setSelectedId(null)
            setRouteOn(false)
          }}
          disabled={analysisOn || !user ? true : false}
        >
          Notification
        </Button>
        <Button
          disabled={user ? false : true}
          variant={activeBtn === 'analysis' ? 'contained' : 'text'}
          color={activeBtn === 'analysis' ? 'info' : 'primary'}
          sx={[
            (theme) =>
              theme.applyStyles('dark', {
                color: 'rgba(255, 255, 255, 0.92)'
              }),

            { padding: '8px 20px' }
          ]}
          value='analysis'
          startIcon={<AssessmentIcon />}
          onClick={(e) => {
            setAnalysisOn(!analysisOn)
            setIsPulled(false)
            setAddressSearch(false)
            handleActive(e)
            setSelectedId(null)
            setRouteOn(false)
          }}
        >
          {analysisOn ? 'Back to View Mode' : 'Analysis Mode'}
        </Button>
        <Button
          disabled={user ? false : true}
          variant={activeBtn === 'animation' ? 'contained' : 'text'}
          color={activeBtn === 'animation' ? 'info' : 'primary'}
          value='animation'
          sx={[
            (theme) =>
              theme.applyStyles('dark', {
                color: 'rgba(255, 255, 255, 0.92)'
              }),
            { padding: '8px 20px' }
          ]}
          startIcon={<AnimationIcon />}
          onClick={(e) => {
            handleActive(e)
            window.open('/cluster-heatmap-animation-lab.html', '_blank')
          }}
        >
          Animation
        </Button>
        <Button
          loading={reportLoading}
          loadingPosition='start'
          disabled={user && !isLoading ? false : true}
          variant={reportBtn ? 'contained' : 'text'}
          color={reportBtn ? 'info' : 'primary'}
          value='report'
          sx={[
            (theme) =>
              theme.applyStyles('dark', {
                color: 'rgba(255, 255, 255, 0.92)'
              }),
            { padding: '8px 20px' }
          ]}
          startIcon={<TextSnippetIcon />}
          onClick={(e) => {
            setReportBtn(true)
            handleActive(e)
            handleReport()
          }}
        >
          User Reports
        </Button>
        <Button
          disabled={user ? false : true}
          variant={routeOn ? 'contained' : 'text'}
          color={routeOn ? 'warning' : 'primary'}
          sx={[
            (theme) =>
              theme.applyStyles('dark', {
                color: 'rgba(255, 255, 255, 0.92)'
              }),
            { padding: '8px 20px' }
          ]}
          startIcon={<RouteIcon />}
          onClick={(e) => {
            setRouteOn(!routeOn)
            setSelectedId(null)
            setAddressSearch(false)
            setIsPulled(false)
          }}
        >
          Route Grader
        </Button>
      </Box>
      <Box>
        <ModeSelect />
      </Box>
    </Box>
  )
}

export default BoardBar
