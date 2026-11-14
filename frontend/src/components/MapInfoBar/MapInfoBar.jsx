import { useState, useEffect, useRef } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Chip from '@mui/material/Chip'
import ModeStandbyIcon from '@mui/icons-material/ModeStandby'
import Checkbox from '@mui/material/Checkbox'
import Divider from '@mui/material/Divider'
import DatePicker from '../DatePicker/DatePicker'
import CircularProgress from '@mui/material/CircularProgress'
import TimePicker from '../DatePicker/TimePicker/TimePicker.tsx'
import Button from '@mui/material/Button'
import AvTimerIcon from '@mui/icons-material/AvTimer'
function MapInfoBar({
  selectedNatures,
  setSelectedNatures,
  filteredListWithLocation,
  filteredListWithoutLocation,
  allType,
  natures,
  onNatureChange,
  dateRange,
  setDateRange,
  isLoading,
  setTimeRange,
  timeRange,
  setAlertContent
}) {
  const [anchorEl, setAnchorEl] = useState(null)
  const [showTimePicker, setShowTimePicker] = useState(false)
  const boxRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      //a function
      if (boxRef.current && !boxRef.current.contains(event.target)) {
        setShowTimePicker(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside) //add a function to window, 1 mouse click and function runs

    return () => {
      document.removeEventListener('mousedown', handleClickOutside) //remove right after it is done
    }
  }, [])
  const open = Boolean(anchorEl)
  const handleClick = (event) => {
    setAnchorEl(event.currentTarget)
  }
  const handleClose = () => {
    setAnchorEl(null)
  }
  //draft time
  const [draftRange, setDraftRange] = useState(timeRange)
  const handleTimeChange = () => {
    if (draftRange) setTimeRange(draftRange)
    setShowTimePicker(false)
  }
  const cancelTimeChange = () => {
    setDraftRange(timeRange)
    setShowTimePicker(false)
  }
  const resetTimeChange = () => {
    setTimeRange(['00:00', '23:59'])
    setShowTimePicker(false)
  }
  const handleToggle = () => {
    if (!showTimePicker) setDraftRange(timeRange) // start from the saved values
    setShowTimePicker(!showTimePicker)
  }
  return (
    <Box
      sx={[
        {
          position: 'relative',
          zIndex: 1000,
          display: 'flex',
          flexGrow: 1,
          alignItems: 'center', //{xs:'flex-end', md:'center'},
          justifyContent: 'right', //{xs:'space-evenly', md:'center'}
          gap: 2,
          // flexDirection:{xs:'column', md:'row'},
          width: { sm: '100%', md: '620px' },
          height: (theme) => theme.mapCustom.mapInfoBarHeight,

          borderBottomLeftRadius: '6px'
        }
      ]}
    >
      <Chip
        sx={{
          '& .MuiChip-label': {
            color: 'white',
            fontWeight: '500'
          },
          bgcolor: '#1976d2',
          '& .MuiSvgIcon-fontSizeMedium': {
            color: 'white'
          },
          '& .MuiCircularProgress-root': {
            color: 'white'
          }
        }}
        icon={isLoading ? <CircularProgress size={22} /> : <ModeStandbyIcon />}
        label={
          filteredListWithLocation.length !== 0
            ? `${filteredListWithLocation.length}/${filteredListWithLocation.length + filteredListWithoutLocation.length}  incidents`
            : '0 incidents'
        }
      />
      <Box ref={boxRef} sx={{ backgroundColor: 'white', borderRadius: 1 }}>
        <Button
          startIcon={<AvTimerIcon />}
          variant='outlined'
          onClick={() => handleToggle()}
          sx={{ width: '250px', color: 'black' }}
        >
          {`Start: ${timeRange[0]} - End: ${timeRange[1]} `}
        </Button>
        {showTimePicker && (
          <Box
            sx={{
              position: 'absolute',
              backgroundColor: 'white',
              borderRadius: '8px',
              padding: '8px',
              top: (theme) =>
                `calc(${theme.mapCustom.mapInfoBarHeight} + 2px) `,
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
              color: 'black'
            }}
          >
            {' '}
            <Box
              sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}
            >
              <TimePicker
                label={'Start: '}
                draftRange={draftRange[0]}
                setDraftRange={setDraftRange}
                index={0}
              />
              <TimePicker
                label={'End: '}
                draftRange={draftRange[1]}
                setDraftRange={setDraftRange}
                index={1}
              />
            </Box>
            <Box
              sx={{ display: 'flex', justifyContent: 'space-around', mt: 1 }}
            >
              <Button
                variant='outlined'
                color='error'
                onClick={cancelTimeChange}
              >
                Cancel
              </Button>
              <Button
                variant='outlined'
                color='warning'
                onClick={resetTimeChange}
              >
                Reset
              </Button>
              <Button variant='contained' onClick={handleTimeChange}>
                Save
              </Button>
            </Box>
          </Box>
        )}
      </Box>
      <Box
        sx={{
          width: '300px',
          '& .m_8fb7ebe7': {
            fontWeight: 500
          }
        }}
      >
        <DatePicker setDateRange={setDateRange} dateRange={dateRange} />
      </Box>

      <Chip
        variant='outlined'
        onClick={handleClick}
        label={
          allType && selectedNatures.length !== 0
            ? 'All types ▾'
            : selectedNatures.length !== 0
              ? `${selectedNatures.length} types ▾`
              : 'No type ▾'
        }
        sx={[
          {
            height: '30px',
            width: '120px',
            fontWeight: 500,
            borderRadius: '4px',
            borderWidth: '1px'
          },
          (theme) =>
            theme.applyStyles('dark', {
              borderColor: 'white'
            }),
          (theme) =>
            theme.applyStyles('light', {
              borderColor: '#424242'
            })
        ]}
      />
      <Menu
        id='incident-type-menu'
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        sx={{
          top: 3,
          '.MuiPaper-root': {
            width: '220px',
            maxHeight: '350px',
            overflowY: 'auto'
          },
          '& .MuiMenuItem-root': {
            height: '40px',
            width: '100%'
          }
        }}
      >
        <MenuItem
          onClick={() => {
            allType === true
              ? setSelectedNatures([])
              : setSelectedNatures(natures)
          }}
        >
          <Checkbox
            checked={selectedNatures.length === natures.length}
            indeterminate={
              selectedNatures.length > 0 &&
              selectedNatures.length < natures.length
            }
          />
          <Typography variant='body1'>
            {selectedNatures.length !== 0 ? 'ALL TYPES' : 'NO TYPE'}
          </Typography>
        </MenuItem>
        <Divider />
        {natures
          ? natures.map((nature) => (
              <MenuItem
                sx={{
                  '& .MuiTypography-root': {
                    textOverflow: 'ellipsis',
                    overflow: 'hidden'
                  }
                }}
                onClick={() => onNatureChange(nature)}
              >
                <Checkbox checked={selectedNatures.includes(nature)} />
                <Typography variant='body1'>{nature}</Typography>
              </MenuItem>
            ))
          : ''}
      </Menu>
    </Box>
  )
}

export default MapInfoBar
