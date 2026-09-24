import { useState } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Chip from '@mui/material/Chip'
import ModeStandbyIcon from '@mui/icons-material/ModeStandby'
import FormControl from '@mui/material/FormControl'
import Select from '@mui/material/Select'
import Checkbox from '@mui/material/Checkbox'
import Divider from '@mui/material/Divider'
function MapInfoBar({
  daysAgo,
  setDaysAgo,
  selectedNatures,
  setSelectedNatures,
  filteredListWithLocation,
  allType,
  natures,
  onNatureChange
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
          width: { sm: '100%', md: '500px' },
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
      <FormControl
        sx={{
          width: '140px',
          '& .MuiFormLabel-root': {
            fontSize: '16px',
            p: 0,
            top: -10
          }
        }}
      >
        <Select
          labelId='demo-simple-select-label'
          id='demo-simple-select'
          value={daysAgo}
          onChange={(e) => setDaysAgo(Number(e.target.value))}
          sx={[
            {
              height: '30px',
              width: '140px',
              fontWeight: 500
            },
            (theme) =>
              theme.applyStyles('dark', {
                '.MuiOutlinedInput-notchedOutline': {
                  borderColor: 'white'
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'white'
                },
                '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'white'
                },
                '.MuiSvgIcon-root': {
                  color: 'white'
                }
              }),
            (theme) =>
              theme.applyStyles('light', {
                '.MuiOutlinedInput-notchedOutline': {
                  borderColor: '#424242'
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#424242'
                },
                '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#424242'
                },
                '.MuiSvgIcon-root': {
                  color: '#424242'
                }
              })
          ]}
        >
          <MenuItem value={3}>3 days ago</MenuItem>
          <MenuItem value={7}>7 days ago</MenuItem>
          <MenuItem value={30}>30 days ago</MenuItem>
        </Select>
      </FormControl>
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
