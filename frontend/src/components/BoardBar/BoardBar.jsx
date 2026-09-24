import ModeSelect from '../ModeSelect/ModeSelect'
import Box from '@mui/material/Box'
import IntList from '../IntList/IntList'
import Button from '@mui/material/Button'
import TravelExploreIcon from '@mui/icons-material/TravelExplore'
import WorkspacesIcon from '@mui/icons-material/Workspaces'

function BoardBar({
  filteredListWithLocation,
  filteredListWithoutLocation,
  getLocation,
  getIncidentID,
  setAddressSearch,
  addressSearch,
  setNoLocationMove,
  setIsPulled,
  incidentColors
}) {
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
          setIsPulled={setIsPulled}
          incidentColors={incidentColors}
        />
        <Button
          sx={(theme) =>
            theme.applyStyles('dark', {
              color: 'rgba(255, 255, 255, 0.92)'
            })
          }
          startIcon={<TravelExploreIcon />}
          onClick={() => setAddressSearch(!addressSearch)}
        >
          Adress Search
        </Button>
        <Button
          sx={(theme) =>
            theme.applyStyles('dark', {
              color: 'rgba(255, 255, 255, 0.92)'
            })
          }
          startIcon={<WorkspacesIcon />}
        >
          DBScan Cluster
        </Button>
        <Button
          sx={(theme) =>
            theme.applyStyles('dark', {
              color: 'rgba(255, 255, 255, 0.92)'
            })
          }
          startIcon={<WorkspacesIcon />}
        >
          Heat map
        </Button>
        <Button> Animation</Button>
      </Box>
      <Box>
        <ModeSelect />
      </Box>
    </Box>
  )
}

export default BoardBar
