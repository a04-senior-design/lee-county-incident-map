import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import { useTheme } from '@mui/material/styles'
import MobileStepper from '@mui/material/MobileStepper'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import KeyboardArrowLeft from '@mui/icons-material/KeyboardArrowLeft'
import KeyboardArrowRight from '@mui/icons-material/KeyboardArrowRight'
import searchhMapIcon from '../../../assets/icon/map-search.svg'
import graphIcon from '../../../assets/icon/graphIcon.svg'
import interactiveIcon from '../../../assets/icon/Select-Location.svg'
import { rgba } from '@mantine/core'
const steps = [
  {
    label: 'Explore Incident Map',
    description:
      'View public activity incidents on an interactive map of Lee County.'
  },
  {
    label: 'Search and Filter Incidents',
    description:
      'Find incidents by location, time, and other available filters.'
  },
  {
    label: 'Generate Map and Export Report',
    description:
      'Visualize incident patterns and export reports for further analysis.'
  }
]
const handleStep = (activeStep) => {
  if (activeStep === 0) {
    return (
      <Box
        sx={{
          width: '100%',
          aspectRatio: '1 / 1',
          height: '500px',
          backgroundColor: ''
        }}
      >
        <img
          src={interactiveIcon}
          alt=''
          style={{ width: '100%', height: '100%' }}
        />
      </Box>
    )
  } else if (activeStep === 1) {
    return (
      <Box
        sx={{
          width: '100%',
          aspectRatio: '1 / 1',
          height: '500px',
          backgroundColor: ''
        }}
      >
        <img
          src={searchhMapIcon}
          alt=''
          style={{ width: '100%', height: '100%' }}
        />
      </Box>
    )
  } else if (activeStep === 2) {
    return (
      <Box
        sx={{
          width: '100%',
          aspectRatio: '1 / 1',
          height: '500px',
          backgroundColor: ''
        }}
      >
        <img src={graphIcon} alt='' style={{ width: '100%', height: '100%' }} />
      </Box>
    )
  }
}

export default function TextMobileStepper() {
  const theme = useTheme()
  const [activeStep, setActiveStep] = useState(0)
  const maxSteps = steps.length

  useEffect(() => {
    const id = setInterval(() => {
      //id act as a ticket number
      setActiveStep((prevActiveStep) => (prevActiveStep + 1) % maxSteps)
    }, 3000)
    return () => clearInterval(id)
  }, [maxSteps])
  return (
    <Box sx={{ flexGrow: 1, height: '100%', display:'flex', flexDirection:'column', alignItems:'center',justifyContent:'space-around' }}>
      <Box
        sx={{
          height: '55%',
          width: '100%',
          display: 'flex'
        }}
      >
        {handleStep(activeStep)}
      </Box>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: 50,
          justifyContent:'center',
          gap:1
        }}
      >
        <Typography
          variant='h2'
          sx={[
            {
              color: 'white',
              fontWeight: 500,
              fontSize: '32px'
            }
          ]}
        >
          {steps[activeStep].label}
        </Typography>
        <Typography
          variant='h4'
          sx={[
            {
              color: 'white',
              fontWeight: 500,
              fontSize: '18px'
            }
          ]}
        >
          {steps[activeStep].description}
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'center'   }}>
        <MobileStepper
          sx={{
            justifyContent: 'center',
            alignItems: 'center',
            gap: 2,
            backgroundColor: 'rgba(245, 245, 245,0.5)',
            width: '100px',
            borderRadius: '50px',
            height: '40px'
          }}
          variant='dots'
          position='static'
          steps={maxSteps}
          activeStep={activeStep}
        />
      </Box>
    </Box>
  )
}
