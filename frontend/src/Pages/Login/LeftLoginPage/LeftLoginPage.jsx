import * as React from 'react'
import Box from '@mui/material/Box'
import { useTheme } from '@mui/material/styles'
import MobileStepper from '@mui/material/MobileStepper'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import KeyboardArrowLeft from '@mui/icons-material/KeyboardArrowLeft'
import KeyboardArrowRight from '@mui/icons-material/KeyboardArrowRight'

const steps = [
  {
    label: 'Select campaign settings',
    description: `For each ad campaign that you create, you can control how much
              you're willing to spend on clicks and conversions, which networks
              and geographical locations you want your ads to show on, and more.`
  },
  {
    label: 'Create an ad group',
    description:
      'An ad group contains one or more ads which target a shared set of keywords.'
  },
  {
    label: 'Create an ad',
    description: `Try out different ad text to see what brings in the most customers,
              and learn how to enhance your ads using features like ad extensions.
              If you run into any problems with your ads, find out how to tell if
              they're running and how to resolve approval issues.`
  }
]

export default function TextMobileStepper() {
  const theme = useTheme()
  const [activeStep, setActiveStep] = React.useState(0)
  const maxSteps = steps.length

  const handleNext = () => {
    setActiveStep((prevActiveStep) => prevActiveStep + 1)
  }

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1)
  }

  return (
    <Box sx={{ flexGrow: 1, height: '100%' }}>
      <Paper
        square
        elevation={0}
        sx={{
          display: 'flex',
          alignItems: 'center',
          height: 50,
          bgcolor: 'background.default',
          justifyContent: 'center'
        }}
      >
        <Typography
          variant='span'
          sx={[
            {
              ml: '4px',
              fontWeight: 500,
              fontSize: '32px',
              color: (theme) => theme.palette.primary.main
            },
            (theme) =>
              theme.applyStyles('dark', {
                color: (theme) => theme.palette.primary.light
              })
          ]}
        >
          {steps[activeStep].label}
        </Typography>
      </Paper>
      <Box
        sx={{
          height: '85%',
          width: '100%',
          maxWidth: '500px',
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        {steps[activeStep].description}
      </Box>
      <MobileStepper
        sx={{ justifyContent: 'center', gap: 2 }}
        variant='progress'
        steps={maxSteps}
        position='static'
        activeStep={activeStep}
        nextButton={
          <Button
            variant='outlined'
            sx={{ borderRadius: '50%', height: 40, width: 40, p: 0 }}
            onClick={handleNext}
            disabled={activeStep === maxSteps - 1}
          >
            {theme.direction === 'rtl' ? (
              <KeyboardArrowLeft />
            ) : (
              <KeyboardArrowRight />
            )}
          </Button>
        }
        backButton={
          <Button
            variant='outlined'
            sx={{ borderRadius: '50%', height: 40, width: 40, p: 0 }}
            onClick={handleBack}
            disabled={activeStep === 0}
          >
            {theme.direction === 'rtl' ? (
              <KeyboardArrowRight />
            ) : (
              <KeyboardArrowLeft />
            )}
          </Button>
        }
      />
    </Box>
  )
}
