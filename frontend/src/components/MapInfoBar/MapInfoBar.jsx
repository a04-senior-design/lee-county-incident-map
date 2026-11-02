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
  timeRange
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
            : '- incidents'
        }
      />
      <Box ref={boxRef} sx={{ backgroundColor: 'white', borderRadius: 1 }}>
        <Button
          startIcon={<AvTimerIcon />}
          variant='outlined'
          onClick={() => setShowTimePicker(!showTimePicker)}
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
              gap: 1,
              color: 'black'
            }}
          >
            <TimePicker
              label={'Start: '}
              timeRange={timeRange[0]}
              setTimeRange={setTimeRange}
              index={0}
            />
            <TimePicker
              label={'End: '}
              timeRange={timeRange[1]}
              setTimeRange={setTimeRange}
              index={1}
            />
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
          allType
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
          <Typography variant='body1'>ALL TYPES</Typography>
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
