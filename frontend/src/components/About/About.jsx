import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ModeSelect from '../ModeSelect/ModeSelect'
import Typography from '@mui/material/Typography'
import AboutContent from './AboutContent/AboutContent'
function About({ aboutPop, setAboutPop }) {
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(255,255,255,0.8)',
        zIndex: 5000,
        position: 'absolute',
        alignItems: 'center',
        justifyContent: 'center',
        display: aboutPop ? 'flex' : 'none',
        flexDirection: 'column'
      }}
    >
      <Box
        sx={[
          {
            width: 'clamp(380px, 40vw, 600px)',
            height: '70%',
            minHeight: '500px',
            background: 'white',
            borderRadius: '16px',

            border: '2px solid',
            borderColor: (theme) => theme.palette.primary.main
          },
          (theme) =>
            theme.applyStyles('light', {
              backgroundColor: '#ffffff'
            }),
          (theme) =>
            theme.applyStyles('dark', {
              backgroundColor: 'rgba(1, 1, 26, 0.92)'
            })
        ]}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            p: 1
          }}
        >
          <Button
            onClick={() => {
              setAboutPop(false)
            }}
          >
            {' '}
            Close
          </Button>
        </Box>

        <Box
          sx={{
            width: '100%',
            height: '90%',

            overflow: 'auto'
          }}
        >
          <AboutContent />
        </Box>
      </Box>
    </Box>
  )
}

export default About
