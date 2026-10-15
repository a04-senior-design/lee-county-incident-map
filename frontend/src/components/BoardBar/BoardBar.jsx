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

  setSelectedId
}) {
  // const [activeBtn, setActiveBtn] = useState({
  //   search: false,
  //   dbscan: false,
  //   heatMap: false,
  //   animation: false
  // })
  const { user } = useAuth()
  const [activeBtn, setActiveBtn] = useState(null)
  const handleActive = (e) => {
    const value = e.currentTarget.value
    setActiveBtn(value)
    console.log('value ', value)
  }

  const [reportLoading, setReportLoading] = useState(false)

  const handleReport = async () => {
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
      const res = await fetch('http://localhost:5001/api/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ incidents, start_date: from, end_date: to })
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `Server error ${res.status}`)
      }
      const blob = await res.blob()
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
          startIcon={<TravelExploreIcon />}
          onClick={() => {
            setAddressSearch(!addressSearch)
            setSelectedId(null)
          }}
          disabled={analysisOn ? true : false}
        >
          Adress Search
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
          disabled={user ? false : true}
          variant={activeBtn === 'report' ? 'contained' : 'text'}
          color={activeBtn === 'report' ? 'info' : 'primary'}
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
            handleActive(e)
            handleReport()
          }}
        >
          User Reports
        </Button>
      </Box>
      <Box>
        <ModeSelect />
      </Box>
    </Box>
  )
}

export default BoardBar
