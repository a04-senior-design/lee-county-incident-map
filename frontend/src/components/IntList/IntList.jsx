import * as React from 'react'
import Box from '@mui/material/Box'
import Drawer from '@mui/material/Drawer'
import Button from '@mui/material/Button'
import KeyboardDoubleArrowRightIcon from '@mui/icons-material/KeyboardDoubleArrowRight'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import PropTypes from 'prop-types'
import IntListContent from './IntListContent/IntListContent'
function CustomTabPanel(props) {
  const { children, value, index, ...other } = props

  return (
    <div
      role='tabpanel'
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: '17px' }}>{children}</Box>}
    </div>
  )
}

CustomTabPanel.propTypes = {
  children: PropTypes.node,
  index: PropTypes.number.isRequired,
  value: PropTypes.number.isRequired
}

function a11yProps(index) {
  return {
    id: `simple-tab-${index}`,
    'aria-controls': `simple-tabpanel-${index}`
  }
}

function IntList({
  listWithLocation,
  listWithoutLocation,
  getLocation,
  getIncidentID,
  setNoLocationMove,
  setIsPulled,
  incidentColors
}) {
  const [open, setOpen] = React.useState(false)

  const toggleDrawer = (newOpen) => () => {
    setOpen(newOpen)
  }
  const [value, setValue] = React.useState(0)

  const handleChange = (event, newValue) => {
    setValue(newValue)
  }

  const theme = useTheme()
  const smallScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const DrawerList = (
    <Box
      sx={[
        {
          width: '400px',
          height: '100%',
          overflow: 'hidden'
        },
        theme.applyStyles('light', {
          backgroundColor: '#fff'
        })
      ]}
    >
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={value}
          onChange={handleChange}
          sx={{
            '& .MuiTabs-indicator': {
              backgroundColor: value === 0 ? '#66bb6a' : ' #f44336' //they use index so 0 is tab 1
            }
          }}
        >
          <Tab
            label='With Location'
            {...a11yProps(0)}
            sx={{
              '&.Mui-selected': {
                color: '#66bb6a',
                fontWeight: 700
              }
            }}
          />
          <Tab
            
            label='Without Location'
            {...a11yProps(1)}
            sx={{
              '&.Mui-selected': {
                color: '#f44336',
                fontWeight: 700
              }
            }}
          />
        </Tabs>
      </Box>
      <CustomTabPanel value={value} index={0}>
        <IntListContent
          incidentList={listWithLocation}
          getLocation={getLocation}
          getIncidentID={getIncidentID}
          latlon={1}
          setNoLocationMove={null}
          incidentColors={incidentColors}
        />
      </CustomTabPanel>
      <CustomTabPanel value={value} index={1}>
        <IntListContent
          incidentList={listWithoutLocation}
          getLocation={getLocation}
          getIncidentID={getIncidentID}
          latlon={0}
          setNoLocationMove={setNoLocationMove}
          incidentColors={incidentColors}
        />
      </CustomTabPanel>
    </Box>
  )
  //console.log(listWithLocation)
  return (
    <div>
      <Button
        variant='outlined'
        startIcon={<KeyboardDoubleArrowRightIcon />}
        onClick={toggleDrawer(() => {
          setOpen(!open)
          setIsPulled(!open)
        })}
        sx={(theme) =>
          theme.applyStyles('dark', {
            color: 'rgba(255, 255, 255, 0.92)',
            borderColor: 'rgba(255, 255, 255, 0.5)'
          })
        }
      >
        Interactive List
      </Button>
      <Drawer //list drawer
        anchor={smallScreen ? 'bottom' : 'left'}
        sx={[
          {
            '& .MuiDrawer-paper': {
              top: (theme) =>
                `calc(100vh - ${theme.mapCustom.listContentHeight})`,
              maxHeight: (theme) => theme.mapCustom.listContentHeight,
              borderTop: '1px solid #0288d1'
            }
          },
          (theme) =>
            theme.applyStyles('dark', {
              '& .MuiDrawer-paper': {
                borderTop: '1px solid #f5f5f5'
              }
            })
        ]}
        variant='persistent'
        open={open}
        onClose={toggleDrawer(false)}
      >
        {DrawerList}
      </Drawer>
    </div>
  )
}
export default IntList
