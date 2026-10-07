import ModeSelect from '../ModeSelect/ModeSelect'
import Box from '@mui/material/Box'
import IntList from '../IntList/IntList'
import Button from '@mui/material/Button'
import TravelExploreIcon from '@mui/icons-material/TravelExplore'
import TextSnippetIcon from '@mui/icons-material/TextSnippet'
import AssessmentIcon from '@mui/icons-material/Assessment'
import { useState } from 'react'
import AnimationIcon from '@mui/icons-material/Animation'
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
  setAnalysisOn
}) {
  // const [activeBtn, setActiveBtn] = useState({
  //   search: false,
  //   dbscan: false,
  //   heatMap: false,
  //   animation: false
  // })
  const [activeBtn, setActiveBtn] = useState(null)
  const handleActive = (e) => {
    const value = e.currentTarget.value
    setActiveBtn(value)
    console.log('value ', value)
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
          onClick={() => setAddressSearch(!addressSearch)}
          disabled={analysisOn ? true : false}
        >
          Adress Search
        </Button>
        <Button
          variant={activeBtn === 'analysis' ? 'contained' : 'text'}
          color={activeBtn === 'analysis' ? 'info' : 'text'}
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
          }}
        >
          {analysisOn? 'Back to View Mode' : 'Analysis Mode'}
        </Button>
        <Button
         variant={activeBtn === 'animation' ? 'contained' : 'text'}
         color={activeBtn === 'animation' ? 'info' : 'text'}
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
          }}
        >
          Animation
        </Button>
        <Button
         variant={activeBtn === 'report' ? 'contained' : 'text'}
         color={activeBtn === 'report' ? 'info' : 'text'}
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
