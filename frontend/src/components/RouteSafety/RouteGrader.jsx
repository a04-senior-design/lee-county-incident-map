import { useEffect, useMemo, useRef, useState } from 'react'
import { useMap, useMapEvents, Polyline, CircleMarker } from 'react-leaflet'
import L from 'leaflet'
import { gradeRoute, scoreColor, scoreLabel } from './routeGrader'
import Card from '@mui/material/Card'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TimelineIcon from '@mui/icons-material/Timeline'
import DirectionsCarFilledIcon from '@mui/icons-material/DirectionsCarFilled'
const TOKEN = import.meta.env.VITE_MAPBOX_TOKEN

async function fetchDrivingRoutes(a, b, signal) {
  const url =
    `https://api.mapbox.com/directions/v5/mapbox/driving/` +
    `${a.lng},${a.lat};${b.lng},${b.lat}` +
    `?geometries=geojson&overview=full&alternatives=true&access_token=${TOKEN}`
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`Directions error ${res.status}`)

  const data = await res.json()
  console.log('routes from Mapbox:', data.routes?.length)
  return (data.routes ?? []).map((route) => ({
    // Mapbox returns [lng, lat]; the grader wants {lat, lng}
    points: route.geometry.coordinates.map(([lng, lat]) => ({ lat, lng })),
    distanceKm: route.distance / 1000,
    minutes: Math.round(route.duration / 60)
  }))
}

export default function RouteGrader({
  active,
  incidents,
  onExit,
  pair,
  type,
  incidentColors
}) {
  const map = useMap()
  const panelRef = useRef(null)
  const [waypoints, setWaypoints] = useState([]) // max 2: start, end
  const [routes, setRoutes] = useState([])
  const [selected, setSelected] = useState(0)
  const [status, setStatus] = useState('')

  useEffect(() => {
    if (panelRef.current) {
      L.DomEvent.disableClickPropagation(panelRef.current)
      L.DomEvent.disableScrollPropagation(panelRef.current)
    }
  }, [active])

  useEffect(() => {
    if (!active) {
      setWaypoints([])
      setRoutes([])
      setStatus('')
      return
    }
    map.getContainer().style.cursor = 'crosshair'
    const onKey = (e) => e.key === 'Escape' && onExit()
    document.addEventListener('keydown', onKey)
    return () => {
      map.getContainer().style.cursor = ''
      document.removeEventListener('keydown', onKey)
    }
  }, [active, map, onExit])

  useMapEvents({
    click(e) {
      if (!active) return
      if (type === 'searchBox') return
      const p = { lat: e.latlng.lat, lng: e.latlng.lng }
      // 3rd click starts a fresh route
      setWaypoints((w) => (w.length >= 2 ? [p] : [...w, p]))
    }
  })
  useEffect(() => {
    if (!pair) return
    const p = { lat: pair[0], lng: pair[1] }
    setWaypoints((prev) => (prev.length >= 2 ? [p] : [...prev, p]))
  }, [pair])
  // Fetch the road route when both points exist
  useEffect(() => {
    if (!active || waypoints.length < 2) {
      setRoutes([])
      return
    }
    const ctrl = new AbortController()
    setStatus('Finding route…')
    fetchDrivingRoutes(waypoints[0], waypoints[1], ctrl.signal)
      .then((r) => {
        setRoutes(r)
        setSelected(0)
        setStatus(r.length ? '' : 'No route found')
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setStatus('Could not get route')
      })
    return () => ctrl.abort()
  }, [waypoints, active])

  const grades = useMemo(
    () => routes?.map((route) => gradeRoute(route.points, incidents)),
    [routes, incidents]
  )

  if (!active) return null
  const grade = grades[selected]
  const color = grade ? scoreColor(grade.score) : '#8ab4f8'
  const route = routes[selected]
  const pickColor = (incident) => {
    const key = (incident.category || '')
    for (const color in incidentColors) {
      if (key.includes(color)) return incidentColors[color]
    }

    return incidentColors.default
  }
  return (
    <>
      {routes.map(
        (r, i) =>
          i !== selected && (
            <Polyline
              key={i}
              positions={r.points.map((p) => [p.lat, p.lng])}
              pathOptions={{
                color: scoreColor(grades[i].score),
                weight: 5,
                opacity: 0.45,
                bubblingMouseEvents: false
              }}
              eventHandlers={{ click: () => setSelected(i) }}
            />
          )
      )}
      {route && (
        <Polyline
          positions={route.points.map((p) => [p.lat, p.lng])}
          pathOptions={{ color, weight: 6, bubblingMouseEvents: false }}
        />
      )}

      {waypoints.map((p, i) => (
        <CircleMarker
          key={i}
          center={[p.lat, p.lng]}
          radius={7}
          interactive={false}
          pathOptions={{
            color: '#000',
            fillColor: i === 0 ? '#27ae60' : '#c53ce7',
            fillOpacity: 1
          }}
        />
      ))}

      {grade?.contributors.map(({ inc }) => (
        <CircleMarker
          key={inc.source_incident_id}
          center={[inc.lat, inc.lon]}
          radius={11}
          interactive={false}
          pathOptions={{ color, weight: 2, fill: false }}
        />
      ))}

      <Box
        ref={panelRef}
        elevation={12}
        sx={[
          {
            position: 'absolute',
            right: 12,
            bottom: 24,
            zIndex: 1000,
            color: '#000',
            padding: 2,
            borderRadius: 3,
            width: 350,
            cursor: 'default',
            border: '2px solid ',
            borderColor: 'rgba(212, 202, 191, 0.92)',
            backgroundColor: 'white'
          },
          (theme) =>
            theme.applyStyles('dark', {
              backgroundColor: 'rgba(1, 1, 26, 0.92)'
            })
        ]}
      >
        <Typography
          variant='h5'
          sx={[
            { fontWeight: 700, textAlign: 'center' },
            (theme) =>
              theme.applyStyles('dark', {
                color: theme.palette.warning.light
              }),
            (theme) =>
              theme.applyStyles('light', {
                color: theme.palette.success.main
              })
          ]}
        >
          Route Safety Grade
        </Typography>
        {routes.length > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'space-around', mt: 2 }}>
            {routes.map((r, i) => (
              <Button
                size='large'
                variant='contained'
                key={i}
                onClick={() => setSelected(i)}
                color={i === selected ? 'success' : 'inherit'}
                sx={[
                  { fontWeight: i === selected ? 700 : 200 },
                  (theme) =>
                    theme.applyStyles('dark', {
                      color: 'white'
                    })
                ]}
              >
                Route {i + 1}: {grades[i].score}
              </Button>
            ))}
          </Box>
        )}
        <Box
          sx={[
            {},
            (theme) =>
              theme.applyStyles('dark', {
                color: 'white'
              })
          ]}
        >
          {status && <Typography sx={{ fontSize: 16 }}>{status}</Typography>}
          {!status && waypoints.length === 0 && (
            <Typography variant='h6' sx={{ fontWeight: 500 }}>
              Click a start point on the map.
            </Typography>
          )}
          {!status && waypoints.length === 1 && (
            <Typography variant='h6' sx={{ fontWeight: 500 }}>
              Now click the end point.
            </Typography>
          )}
        </Box>

        {grade && route && (
          <>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column'
              }}
            >
              <Box>
                <Typography
                  variant='span'
                  sx={{ fontSize: 36, fontWeight: 700, color }}
                >
                  {grade.score}
                </Typography>
                <Typography
                  variant='span'
                  sx={{ fontSize: 16, fontWeight: 700, color: '#9e9e9e' }}
                >
                  {' '}
                  /100
                </Typography>
              </Box>

              <Typography sx={{ color }}>{scoreLabel(grade.score)}</Typography>
            </Box>
            <Box
              sx={[
                {
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 2
                },
                (theme) =>
                  theme.applyStyles('dark', {
                    color: '#e0e0e0'
                  })
              ]}
            >
              <Typography
                variant='h6'
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <TimelineIcon />
                {route.distanceKm.toFixed(1)} km
              </Typography>
              <Typography
                variant='h6'
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <DirectionsCarFilledIcon />
                {route.minutes} mins drive
              </Typography>
            </Box>
            <Box
              sx={[
                {
                  textAlign: 'center'
                },
                (theme) =>
                  theme.applyStyles('dark', {
                    color: '#e0e0e0'
                  })
              ]}
            >
              <Typography
                variant='span'
                sx={{
                  textAlign: 'center',
                  fontSize: 20,
                  fontWeight: 700,
                  color
                }}
              >
                {grade.contributors.length}{' '}
              </Typography>
              <Typography
                variant='span'
                sx={[
                  { textAlign: 'center', color: '#424242', fontSize: 14 },
                  (theme) =>
                    theme.applyStyles('dark', {
                      color: '#e0e0e0'
                    })
                ]}
              >
                {' '}
                incidents within 400 meters
              </Typography>
            </Box>

            <Typography
              sx={[
                { fontSize: '16px', fontWeight: 600 },
                (theme) =>
                  theme.applyStyles('dark', {
                    color: '#e0e0e0'
                  })
              ]}
            >
              Biggest Fators:
            </Typography>
            <Box
              component='ul'
              sx={[
                {
                  mt: 1,
                  fontSize: 12,
                  '& li': {
                    listStyle: 'none'
                  }
                },
                (theme) =>
                  theme.applyStyles('dark', {
                    color: '#9e9e9e'
                  })
              ]}
            >
              {grade.contributors
                .filter((c) => c.pts > 0)
                .slice(0, 5)
                .map(({ inc, pts, d }) => (
                  <Box
                    key={inc.source_incident_id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between'
                    }}
                  >
                    <Box sx={{display:'flex', alignItems:'center', gap:1}}>
                      <Box
                        sx={{
                          bgcolor: () => pickColor(inc),
                          width: '20px',
                          height: '20px',
                          borderRadius: '50%'
                        }}
                      ></Box>
                      <Typography
                        variant='h6'
                        sx={[
                          { fontSize: '16px' },
                          (theme) =>
                            theme.applyStyles('dark', {
                              color: '#e0e0e0'
                            })
                        ]}
                      >
                        {inc.nature}
                      </Typography>
                    </Box>

                    <Typography
                      sx={[
                        { fontSize: '14px' },
                        (theme) =>
                          theme.applyStyles('dark', {
                            color: '#e0e0e0'
                          })
                      ]}
                    >
                      {Math.round(d)} m · −
                      {pts < 1 ? pts.toFixed(1) : Math.round(pts)}
                    </Typography>
                  </Box>
                ))}
            </Box>
          </>
        )}
        <Box
          sx={{
            mt: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-around'
          }}
        >
          <Button
            variant='outlined'
            onClick={() => setWaypoints((w) => w.slice(0, -1))}
          >
            Undo
          </Button>{' '}
          <Button
            variant='outlined'
            color='warning'
            onClick={() => setWaypoints([])}
          >
            Clear
          </Button>{' '}
          <Button variant='contained' color='error' onClick={onExit}>
            Exit
          </Button>
        </Box>
      </Box>
    </>
  )
}
