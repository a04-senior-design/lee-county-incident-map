import { useEffect, useMemo, useRef, useState } from 'react'
import { useMap, useMapEvents, Polyline, CircleMarker } from 'react-leaflet'
import L from 'leaflet'
import { gradeRoute, scoreColor, scoreLabel } from './routeGrader'

const TOKEN = import.meta.env.VITE_MAPBOX_TOKEN

async function fetchDrivingRoute(a, b, signal) {
  const url =
    `https://api.mapbox.com/directions/v5/mapbox/driving/` +
    `${a.lng},${a.lat};${b.lng},${b.lat}` +
    `?geometries=geojson&overview=full&access_token=${TOKEN}`
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`Directions error ${res.status}`)
  const data = await res.json()
  const r = data.routes?.[0]
  if (!r) return null
  return {
    // Mapbox returns [lng, lat]; the grader wants {lat, lng}
    points: r.geometry.coordinates.map(([lng, lat]) => ({ lat, lng })),
    distanceKm: r.distance / 1000,
    minutes: Math.round(r.duration / 60)
  }
}

export default function RouteGrader({ active, incidents, onExit, pair, type }) {
  const map = useMap()
  const panelRef = useRef(null)
  const [waypoints, setWaypoints] = useState([]) // max 2: start, end
  const [route, setRoute] = useState(null)
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
      setRoute(null)
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
    if(!pair) return
    const p = { lat: pair[0], lng: pair[1] }
    setWaypoints((prev) => (prev.length >= 2 ? [p] : [...prev, p]))
  }, [pair])
  // Fetch the road route when both points exist
  useEffect(() => {
    if (!active || waypoints.length < 2) {
      setRoute(null)
      return
    }
    const ctrl = new AbortController()
    setStatus('Finding route…')
    fetchDrivingRoute(waypoints[0], waypoints[1], ctrl.signal)
      .then((r) => {
        setRoute(r)
        setStatus(r ? '' : 'No route found')
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setStatus('Could not get route')
      })
    return () => ctrl.abort()
  }, [waypoints, active])

  const grade = useMemo(
    () => (route ? gradeRoute(route.points, incidents) : null),
    [route, incidents]
  )

  if (!active) return null
  const color = grade ? scoreColor(grade.score) : '#8ab4f8'

  return (
    <>
      {route && (
        <Polyline
          positions={route.points.map((p) => [p.lat, p.lng])}
          pathOptions={{ color, weight: 6 }}
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

      <div
        ref={panelRef}
        style={{
          position: 'absolute',
          right: 12,
          bottom: 24,
          zIndex: 1000,
          background: '#fff',
          color: '#000',
          padding: 12,
          borderRadius: 8,
          width: 250
        }}
      >
        <b>Route Safety Grade</b>
        {status && <p style={{ fontSize: 12 }}>{status}</p>}
        {!status && waypoints.length === 0 && (
          <p style={{ fontSize: 12 }}>Click a start point on the map.</p>
        )}
        {!status && waypoints.length === 1 && (
          <p style={{ fontSize: 12 }}>Now click the end point.</p>
        )}
        {grade && route && (
          <>
            <div style={{ fontSize: 36, fontWeight: 700, color }}>
              {grade.score}/100
            </div>
            <div style={{ color }}>{scoreLabel(grade.score)}</div>
            <div style={{ fontSize: 12 }}>
              {route.distanceKm.toFixed(1)} km · {route.minutes} min drive ·{' '}
              {grade.contributors.length} incidents within 400 m
            </div>
            <ul style={{ fontSize: 12, paddingLeft: 16 }}>
              {grade.contributors
                .filter((c) => c.pts > 0)
                .slice(0, 5)
                .map(({ inc, pts, d }) => (
                  <li key={inc.source_incident_id}>
                    {inc.nature} · {Math.round(d)} m · −
                    {pts < 1 ? pts.toFixed(1) : Math.round(pts)}
                  </li>
                ))}
            </ul>
          </>
        )}
        <button onClick={() => setWaypoints((w) => w.slice(0, -1))}>
          Undo
        </button>{' '}
        <button onClick={() => setWaypoints([])}>Clear</button>{' '}
        <button onClick={onExit}>Exit</button>
      </div>
    </>
  )
}
