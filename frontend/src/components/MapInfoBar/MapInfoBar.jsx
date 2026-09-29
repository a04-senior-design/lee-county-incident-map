import { useState } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Chip from '@mui/material/Chip'
import ModeStandbyIcon from '@mui/icons-material/ModeStandby'
import Checkbox from '@mui/material/Checkbox'
import Divider from '@mui/material/Divider'
import DatePicker from '../DatePicker/DatePicker'
function MapInfoBar({
  selectedNatures,
  setSelectedNatures,
  filteredListWithLocation,
  allType,
  natures,
  onNatureChange,
  dateRange,
  setDateRange
}) {
  const [anchorEl, setAnchorEl] = useState(null)
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
          alignItems: 'center', //{xs:'flex-end', md:'center'},
          justifyContent: 'right', //{xs:'space-evenly', md:'center'}
          gap: 2,
          // flexDirection:{xs:'column', md:'row'},
          width: { sm: '100%', md: '570px' },
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
          }
        }}
        icon={<ModeStandbyIcon />}
        label={
          filteredListWithLocation.length !== 0
            ? `${filteredListWithLocation.length} incidents`
            : '- incidents'
        }
      />
     
      <Box
        sx={{
          width: '900px',
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
