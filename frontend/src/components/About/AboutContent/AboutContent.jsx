import * as React from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import Typography from '@mui/material/Typography'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'

/* ---------- small presentational helpers ---------- */

const listSx = {
  m: 0,
  pl: 3,
  '& li': { mb: 0.75, lineHeight: 1.55 },
  '& li:last-child': { mb: 0 },
  '& li::marker': { fontWeight: 600, color: 'primary.main' },
}

function Section({ title, children }) {
  return (
    <Box sx={{ mt: 2.5, '&:first-of-type': { mt: 0 } }}>
      <Typography
        variant='subtitle2'
        component='h4'
        sx={{
          mb: 1,
          fontWeight: 700,
          letterSpacing: 0.4,
          textTransform: 'uppercase',
          color: 'text.secondary',
        }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  )
}

function Steps({ children }) {
  return (
    <Typography variant='body2' component='ol' sx={listSx}>
      {children}
    </Typography>
  )
}

function Bullets({ children }) {
  return (
    <Typography variant='body2' component='ul' sx={listSx}>
      {children}
    </Typography>
  )
}

function Term({ children }) {
  return (
    <Box component='strong' sx={{ fontWeight: 700 }}>
      {children}
    </Box>
  )
}

function Code({ children }) {
  return (
    <Box
      component='code'
      sx={{
        px: 0.75,
        py: 0.1,
        borderRadius: 0.75,
        bgcolor: 'action.hover',
        fontFamily: 'monospace',
        fontSize: '0.85em',
      }}
    >
      {children}
    </Box>
  )
}

function Intro({ children }) {
  return (
    <Typography variant='body2' sx={{ lineHeight: 1.6, mb: 2 }}>
      {children}
    </Typography>
  )
}

function Limits({ title = 'Limits', children }) {
  return (
    <Alert severity='warning' variant='outlined' sx={{ mt: 2.5, fontSize: '0.875rem' }}>
      <Typography variant='subtitle2' component='div' sx={{ fontWeight: 700, mb: 0.5 }}>
        {title}
      </Typography>
      {children}
    </Alert>
  )
}

function Panel({ id, name, defaultExpanded = false, children }) {
  return (
    <Accordion defaultExpanded={defaultExpanded} disableGutters>
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        aria-controls={`${id}-${name}-content`}
        id={`${id}-${name}-header`}
      >
        <Typography component='span' sx={{ fontWeight: 600 }} >
          {children[0]}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 2 }}>{children[1]}</AccordionDetails>
    </Accordion>
  )
}

/* ---------- component ---------- */

export default function AccordionUsage() {
  const id = React.useId()

  return (
    <div>
      {/* 1. Analysis Mode */}
      <Panel id={id} name='analysis' defaultExpanded>
        {'About the Analysis Mode'}
        <>
          <Intro>
            The Analysis Mode provides analyses to visualize clusters, spatial
            distributions, and hot spots of incidents for a date range.
          </Intro>

          <Section title='How to use it'>
            <Steps>
              <li>Choose an analysis (shown as a series of radio buttons).</li>
              <li>
                Click “Date range” and pick a start and end day on the calendar.
                You can also set start and end times.
              </li>
              <li>
                Optionally, choose from the dropdown menu which incident types
                to include.
              </li>
              <li>
                Adjust the analysis settings (such as the bandwidth slider for
                the “KDE Heat Map”). The map updates automatically.
              </li>
              <li>
                For the KDE analyses, optionally click Optimized Bandwidth to
                have the bandwidths chosen automatically from the data.
              </li>
            </Steps>
          </Section>

          <Section title='The analyses'>
            <Bullets>
              <li>
                <Term>Cluster Analysis</Term> groups nearby incidents using
                DBSCAN (Density-Based Spatial Clustering of Applications with
                Noise) at three scales: District, Neighborhood and Street. You
                can turn each scale on or off. Move its slider toward Dense for
                smaller, tighter clusters; move its slider toward Sparse for
                larger, sparser clusters.
              </li>
              <li>
                <Term>KDE Heat Map (all points)</Term> uses Kernel Density
                Estimation (KDE) to show incident density as a smooth surface. A
                larger bandwidth gives a smoother, more spread-out map.
              </li>
              <li>
                <Term>KDE Heat Map (by cluster density level)</Term> uses your
                most recent Cluster Analysis results, with a separate bandwidth
                for each cluster level. Run Cluster Analysis before selecting
                this option. Incidents that Cluster Analysis marks as noise are
                not included.
              </li>
              <li>
                <Term>Getis-Ord Gi* Heat Map</Term> highlights statistically
                significant hot spots in red and cold spots in blue. The
                distance band sets how far around each grid cell its neighbors
                are counted.
              </li>
            </Bullets>
          </Section>

          <Limits title='Analysis Mode limits'>
            Cluster Analysis can cover at most 60 days. Cluster Analysis results
            expire after one hour, so run it again if KDE Heat Map (by cluster
            density level) shows an error.
          </Limits>
        </>
      </Panel>

      {/* 2. Before You Animate */}
      <Panel id={id} name='before-animate'>
        {'Before You Animate: Using Analysis Mode to Help Choose Settings'}
        <>
          <Intro>
            Analysis Mode shows one analysis for one date range. It is
            recommended that you use it to explore your data and choose settings
            before you build an animation.
          </Intro>

          <Steps>
            <li>
              <Term>Try a window size.</Term> In Analysis Mode, set the date
              range to the length of a possible animation window, such as one
              week, to see whether a window shows you meaningful clusters and/or
              heat maps for your evaluation.
            </li>
            <li>
              <Term>Tune the settings.</Term> Adjust the cluster sliders,
              bandwidth or distance band until the map shows meaningful
              patterns. For the KDE analyses, you can optionally click Optimized
              Bandwidth to get a starting value chosen from the data. Write down
              the settings you like.
            </li>
            <li>
              <Term>
                For KDE Heat Map (by cluster density level), check the cluster
                density categories.
              </Term>{' '}
              Look at which cluster density categories produce clusters in your
              first window. Turn off any scale that doesn’t, so the animation
              doesn’t potentially stop with an error.
            </li>
            <li>
              <Term>Build the animation.</Term> Switch to the animation mode,
              choose the same analysis and enter the same settings. Then set the
              date range, window size and time step, keeping to 30 frames or
              fewer.
            </li>
            <li>
              <Term>Look closer.</Term> When a frame stands out, hover over its
              date to see its full date range. Then enter that range in Analysis
              Mode to examine it in detail.
            </li>
          </Steps>
        </>
      </Panel>

      {/* 3. Animation */}
      <Panel id={id} name='animation'>
        {'About the Animation'}
        <>
          <Intro>
            The animation shows how incident patterns change over time. The date
            range you pick is split into time windows, and each window becomes
            one frame of the animation. Each frame starts one time step after
            the start of the previous frame.
          </Intro>

          <Section title='How to use it'>
            <Steps>
              <li>Choose an analysis (shown as a series of radio buttons).</li>
              <li>
                Click “Date range” and pick a start and end day on the calendar.
                You can also set start and end times.
              </li>
              <li>
                Enter a window size and time step, such as <Code>7D</Code> and{' '}
                <Code>1D</Code>. Use <Code>h</Code> for hours, <Code>D</Code>{' '}
                for days, <Code>W</Code> for weeks, <Code>MS</Code> for months
                and <Code>YS</Code> for years. For full calendar months or
                years, start the date range on the 1st of a month (
                <Code>MS</Code>) or on January 1 (<Code>YS</Code>). When the
                time step is smaller than the window size, the windows overlap,
                so each frame shares some incidents with the next and the map
                changes more gradually.
              </li>
              <li>
                Optionally, choose from the dropdown menu which incident types
                to include.
              </li>
              <li>
                Adjust the analysis settings (such as the bandwidth slider for
                the “KDE Heat Map”), then click Apply.
              </li>
              <li>
                Use play, the step buttons, the slider and the speed buttons to
                move through the frames. Hover over the date below the slider to
                see a frame’s full date range.
              </li>
            </Steps>
          </Section>

          <Section title='The animation analyses'>
            <Typography variant='body2' sx={{ lineHeight: 1.6 }}>
              Refer to the analyses described in the About the Analysis Mode
              section.
            </Typography>
          </Section>

          <Limits title='Animation limits'>
            An animation can have at most 30 frames. Analysis parameters set by
            the user are applied to each frame. KDE Heat Map (by cluster density
            level) needs every frame to have clusters at the same scales as the
            first frame. If a scale has clusters in some frames but not others,
            an error appears. Try turning that scale off or changing its slider.
          </Limits>
        </>
      </Panel>

      {/* 4. User Reports */}
      <Panel id={id} name='reports'>
        {'About the User Reports'}
        <>
          <Typography variant='body2' sx={{ lineHeight: 1.6 }}>
            The user report feature provides a registered user the ability to
            generate a downloadable PDF of data and maps straight from the live
            site. The user’s set analyses, viewport, incident choices, and time
            frame are captured and streamed to the PDF as PNG charts and maps.
            Users can visually see trends and read summaries of that data to
            identify how incidents change over time, what specific incidents are
            happening around them, and discover the top hotspots not only in
            their selected region, but all of Lee County.
          </Typography>
        </>
      </Panel>
    </div>
  )
}
