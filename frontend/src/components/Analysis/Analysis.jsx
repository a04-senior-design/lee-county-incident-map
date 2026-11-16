import { useEffect, useRef, useState } from 'react'
import './Analysis.css'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

import Typography from '@mui/material/Typography'
import Switch from '@mui/material/Switch'
import Slider from '@mui/material/Slider'
import Card from '@mui/material/Card'
import Button from '@mui/material/Button'
import Radio from '@mui/material/Radio'
import RadioGroup from '@mui/material/RadioGroup'
import FormControlLabel from '@mui/material/FormControlLabel'
import FormControl from '@mui/material/FormControl'
import FormLabel from '@mui/material/FormLabel'
import Box from '@mui/material/Box'

// Relative on purpose: the Vite proxy (dev) and nginx (prod) forward /api to the droplet.
const API = '/api/v1'

const LEVEL_DRAW_ORDER = ['district', 'neighborhood', 'street']
const LEVEL_UI_ORDER = ['district', 'neighborhood', 'street'] // order of the control blocks

const LEVEL_STYLES = {
  district: {
    fillOpacity: 0.07,
    weight: 1,
    opacity: 0.45,
    pointRadius: 4,
    noiseRadius: 2
  },
  neighborhood: {
    fillOpacity: 0.14,
    weight: 1.5,
    opacity: 0.65,
    pointRadius: 6,
    noiseRadius: 3
  },
  street: {
    fillOpacity: 0.26,
    weight: 2,
    opacity: 0.85,
    pointRadius: 8,
    noiseRadius: 4
  }
}

const LEVEL_LABELS = {
  district: 'District',
  neighborhood: 'Neighborhood',
  street: 'Street'
}

const LEVEL_HINTS = {
  street: 'micro · 300–2500 ft',
  neighborhood: 'meso · 0.5–2 mi',
  district: 'macro · 2–6 mi'
}

const LEVEL_PRESETS = {
  district: { epsMax: 30000, epsMin: 10000 },
  neighborhood: { epsMax: 9990, epsMin: 3000 },
  street: { epsMax: 2990, epsMin: 300 }
}

const CLUSTER_STATUS_NOTES = {
  missing:
    '*Run cluster analysis first to unlock KDE(By cluster density level)',
  no_cluster_levels:
    'Last cluster run found only noise. Try larger epsilon values in Cluster Analysis.',
  all_noise:
    'Last cluster run found only noise. Try larger epsilon values in Cluster Analysis.'
}

const EMPTY_LEVELS = { district: null, neighborhood: null, street: null }
const ALL_VISIBLE = { district: true, neighborhood: true, street: true }
const DEFAULT_LEVEL_SLIDERS = {
  district: 20000,
  neighborhood: 6500,
  street: 1400
}
// Outside the component so it survives the legend being rebuilt on every data change
let legendCollapsed = false
// ---------- pure helpers (same names as before) ----------
function levelToParams(level, sliderVal) {
  const p = LEVEL_PRESETS[level]
  // slider value is in feet; Sparse (left) = epsMax, Dense (right) = epsMin
  return { eps: p.epsMax + p.epsMin - sliderVal }
}

// Returns the layer group (the caller adds/removes it from the map)
function renderLevelLayer(level, geojson) {
  const st = LEVEL_STYLES[level]

  const polygons = geojson.features.filter(
    (f) => f.properties.feature_type === 'polygon'
  )
  const pts = geojson.features.filter(
    (f) => f.properties.feature_type === 'point'
  )

  const group = L.layerGroup()

  L.geoJSON(
    { type: 'FeatureCollection', features: polygons },
    {
      style: (feature) => ({
        fillColor: feature.properties.color,
        color: feature.properties.color,
        fillOpacity: st.fillOpacity,
        weight: st.weight,
        opacity: st.opacity
      }),
      onEachFeature: (feature, layer) => {
        layer.bindTooltip(
          `[${LEVEL_LABELS[level]}] Cluster ${feature.properties.cluster_id} — ${feature.properties.point_count} incidents`,
          { sticky: true }
        )
      }
    }
  ).addTo(group)

  L.geoJSON(
    { type: 'FeatureCollection', features: pts },
    {
      pointToLayer: (feature, latlng) =>
        L.circleMarker(latlng, {
          radius:
            feature.properties.cluster_id === -1
              ? st.noiseRadius
              : st.pointRadius,
          fillColor: feature.properties.color,
          color: '#fff',
          weight: 0.5,
          fillOpacity: feature.properties.cluster_id === -1 ? 0.35 : 0.85
        }),
      onEachFeature: (feature, layer) => {
        const label =
          feature.properties.cluster_id === -1
            ? `[${LEVEL_LABELS[level]}] Noise`
            : `[${LEVEL_LABELS[level]}] Cluster ${feature.properties.cluster_id}`

        layer.bindTooltip(label, { sticky: true })
      }
    }
  ).addTo(group)

  return group
}

// Returns the legend rows as an HTML string (the effect wraps it in the collapsible control)
function buildClusterLegend(levelData, levelVisible) {
  return LEVEL_DRAW_ORDER.filter(
    (level) => levelData[level] && levelVisible[level]
  )
    .map((level) => {
      const polygons = levelData[level].features.filter(
        (f) => f.properties.feature_type === 'polygon'
      )

      if (!polygons.length) return ''

      const rows = polygons
        .map(
          (f) =>
            `<div><span class="legend-swatch" style="background:${f.properties.color}"></span>` +
            `Cluster ${f.properties.cluster_id} — ${f.properties.point_count} pts</div>`
        )
        .join('')

      return (
        `<div class="legend-section">` +
        `<strong class="legend-section-title">${LEVEL_LABELS[level]}</strong>` +
        `${rows}</div>`
      )
    })
    .join('')
}

// startDate / endDate: optional 'YYYY-MM-DD' strings for /clusters.
// Leave them out and the server uses the last 30 days. The server caps a range at 60 days.
const Analysis = ({
  active,
  startDate,
  endDate,
  setIsLoading,
  areaBounds,
  drawArea,
  reportMapState,
  setReportMapState,
  selectedNatures,
  showAlert,
  isLoading
}) => {
  const map = useMap()
  const bbox = areaBounds ? areaBounds.toBBoxString() : null
  const natureKey = Array.isArray(selectedNatures)
    ? selectedNatures.join(',')
    : (selectedNatures ?? '')
  const noTypes = Array.isArray(selectedNatures) && selectedNatures.length === 0
  //Mode --------------
  const [mode, setMode] = useState('kde-heatmap')
  const [currentClusterSet, setCurrentClusterSet] = useState(0)
  const [clusterSetLabels, setClusterSetLabels] = useState([])
  const [dataVersion, setDataVersion] = useState(0) // bumps when the date range changes
  const [dbscanRunId, setDbscanRunId] = useState(null)
  // KDE
  const [kdeData, setKdeData] = useState(null) // last KDE response
  const [dbscanStatus, setDbscanStatus] = useState(null)
  const [bandwidths, setBandwidths] = useState([]) // was `sliders` / `valueLabels`
  const [runTiers, setRunTiers] = useState([])

  // DBSCAN / clusters
  const [levelVisible, setLevelVisible] = useState(ALL_VISIBLE)
  const [levelSliders, setLevelSliders] = useState(DEFAULT_LEVEL_SLIDERS)
  const [levelData, setLevelData] = useState(EMPTY_LEVELS)
  const [status, setStatusState] = useState(null) // 'loading' | 'ready' | 'error'
  const [dbscanError, setDbscanError] = useState('')

  const activeTiers = LEVEL_DRAW_ORDER.filter((l) => levelVisible[l])
  //GI-Star
  const [GISData, setGISData] = useState(null) // last KDE response

  const [distanceBand, setDistanceBand] = useState(2500) // was `sliders` / `valueLabels`
  const distanceBandTimeBound = useRef(null)
  //REF
  const gistarRequestRef = useRef(0)
  const applyRef = useRef(null)
  const debounceTimerRef = useRef(null)
  const clustersLoadedRef = useRef(false)
  const kdeRequestRef = useRef(0)
  const dbscanRequestRef = useRef(0)
  const lastKdeKeyRef = useRef('')
  const lastRangeRef = useRef('') // last start/end date pair we reacted to
  // run_id from the last /clusters call. The server keeps that run for 1 hour and
  // /kde-heatmap needs it to know which cluster results to use.
  const runIdRef = useRef(null)
  //prevent when using the slider on the lab, the map can be dragged
  const topBarRef = useRef(null)
  const secondBarRef = useRef(null)
  const thirdBarRef = useRef(null)
  //State valid-----------------------------------------------
  const kdeValid = kdeData
    ? kdeData.cluster_set === 1
      ? 'cluster'
      : 'all'
    : null
  const clusterValid = LEVEL_DRAW_ORDER.some((l) => levelData[l])
  const gistarValid = !!GISData

  useEffect(() => {
    if (active) return
    // leaving Analysis Mode: back to "no valid maps" (diagram: ⊗)
    setKdeData(null)
    setGISData(null)
    setLevelData(EMPTY_LEVELS)
    setDbscanStatus('missing')
    setCurrentClusterSet(0)
    setMode('kde-heatmap') // re-entering starts at KDE (all points), like the diagram's A
    setLevelVisible(ALL_VISIBLE)
    setLevelSliders(DEFAULT_LEVEL_SLIDERS)
    runIdRef.current = null
    setDbscanRunId(null)

    clustersLoadedRef.current = false
    lastRangeRef.current = '' // so the range effect refetches on re-entry
    lastKdeKeyRef.current = ''
    kdeRequestRef.current++ // ignore requests still in flight
    gistarRequestRef.current++
    dbscanRequestRef.current++
  }, [active])

  useEffect(() => {
    setReportMapState(
      active
        ? {
            kde: kdeValid,
            clusters: clusterValid,
            giStar: gistarValid,
            kdeRunId: kdeData?.run_id ?? null,
            dbscanRunId: clusterValid ? dbscanRunId : null,
            giStarRunId: GISData?.run_id ?? null
          }
        : {
            kde: null,
            clusters: false,
            giStar: false,
            kdeRunId: null,
            dbscanRunId: null,
            giStarRunId: null
          }
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    active,
    kdeValid,
    clusterValid,
    gistarValid,
    kdeData,
    GISData,
    dbscanRunId
  ])

  useEffect(() => {
    const els = [
      topBarRef.current,
      secondBarRef.current,
      thirdBarRef.current
    ].filter(Boolean)

    els.forEach((el) => {
      L.DomEvent.disableScrollPropagation(el)
      L.DomEvent.on(el, 'dblclick', L.DomEvent.stopPropagation)
    })

    return () =>
      els.forEach((el) =>
        L.DomEvent.off(el, 'dblclick', L.DomEvent.stopPropagation)
      )
  }, [])
  function setStatus(state) {
    setStatusState(state)
  }

  // The old POST /analysis is gone: the server reads the incidents itself and only needs
  // the date range. This is the old "incident list changed" effect, now keyed on the dates.
  useEffect(() => {
    if (!active) return

    const range = `${startDate ?? ''}|${endDate ?? ''}|${bbox ?? ''}|${natureKey}`
    if (range === lastRangeRef.current) return // same range, nothing to refetch
    lastRangeRef.current = range

    setKdeData(null) // avoid showing the old heat map while the new one loads
    setGISData(null)
    // the old cluster run was for the old range, so drop it
    runIdRef.current = null
    setDbscanRunId(null)
    clustersLoadedRef.current = false
    setLevelData(EMPTY_LEVELS)
    setDbscanStatus('missing')
    setCurrentClusterSet(0)

    setDataVersion((v) => v + 1) // makes the KDE and cluster effects fetch again
  }, [startDate, endDate, active, bbox, natureKey])

  // ---------- KDE ----------
  // >= 100: nearest whole number. < 100: two significant digits.
  function formatTick(t) {
    if (Math.abs(t) >= 100) return Math.round(t)
    return Number(t.toPrecision(2))
  }
  function fetchKDEHeatmap(
    bandwidthsParam,
    clusterSet,
    runId = runIdRef.current,
    optimize = false
  ) {
    if (noTypes) {
      setKdeData(null)

      return
    }
    setIsLoading(true)
    const params = new URLSearchParams()

    if (clusterSet !== undefined && clusterSet !== null) {
      params.append('cluster_set', clusterSet)
    }

    // cluster_set=1 needs it, and with it dbscan_status can report "available"
    if (runId) params.append('run_id', runId)

    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    if (selectedNatures?.length) {
      params.append(
        'category',
        Array.isArray(selectedNatures)
          ? selectedNatures.join(',')
          : selectedNatures
      )
    }
    if (optimize) {
      params.append('optimize', 'true') // never send bandwidth together with this
    } else if (bandwidthsParam) {
      bandwidthsParam.forEach((bw) => params.append('bandwidth', bw))
    }
    if (bbox) params.append('bbox', bbox)
    const query = params.toString()
    const url = query ? `${API}/kde-heatmap?${query}` : `${API}/kde-heatmap`

    const id = ++kdeRequestRef.current

    fetch(url)
      .then(async (res) => {
        if (res.status === 504) {
          const err = new Error(
            'Optimizing took too long and the server timed out.'
          )
          err.data = {}
          throw err
        }
        const data = await res.json()

        if (!res.ok) {
          const err = new Error(data.error || `HTTP ${res.status}`)
          err.data = data
          throw err
        }
        return data
      })
      .then((data) => {
        if (id !== kdeRequestRef.current) return // stale response

        setKdeData(data) // the overlay effect draws it (renderKDEHeatmap)
        setClusterSetLabels(data.cluster_set_labels ?? [])
        setDbscanStatus(data.dbscan_status ?? null) // replaces updateClusterAvailability
        setBandwidths(data.bandwidths ?? []) // replaces buildSliders' DOM work

        if (data.cluster_set !== undefined && data.cluster_set !== clusterSet) {
          setCurrentClusterSet(data.cluster_set)
        }
        if (optimize) showAlert('success', 'Bandwidth Optimized successfully!')
      })
      .catch((err) => {
        if (id !== kdeRequestRef.current) return
        console.error('KDEHeatmap fetch failed: ', err)

        if (err.data) setDbscanStatus(err.data.dbscan_status ?? null)
        showAlert('error', err.message)
        // the run expired (the server keeps runs for 1 hour) or was never made:
        // forget it and fall back to the plain heat map
        if (
          clusterSet === 1 &&
          (err.data?.dbscan_status === 'missing' || /run_id/i.test(err.message))
        ) {
          runIdRef.current = null
          setDbscanRunId(null)
          clustersLoadedRef.current = false
          setDbscanStatus('missing')
          setCurrentClusterSet(0)
        }
      })
      .finally(() => {
        if (id === kdeRequestRef.current) setIsLoading(false)
      })
  }

  useEffect(() => {
    if (!active || mode !== 'kde-heatmap') return
    if (dataVersion === 0) return // wait for the date-range effect to run once

    const key = `${dataVersion}-${currentClusterSet}`
    if (key === lastKdeKeyRef.current && kdeData) return // already have it
    lastKdeKeyRef.current = key

    fetchKDEHeatmap(null, currentClusterSet)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, mode, currentClusterSet, dataVersion])

  // Draws the overlay + legend, returns a cleanup function
  function renderKDEHeatmap(data) {
    const b = data.bounds
    const imageBounds = [
      [b.south, b.west],
      [b.north, b.east]
    ]

    const overlayLayer = L.imageOverlay(data.image, imageBounds, {
      opacity: 0.8
    })

    const legend = data.legend
    const gradientCss = `linear-gradient(to right, ${legend.colors.join(', ')})`

    const tickLabels = legend.ticks
      .map((t) => `<span>${formatTick(t)}</span>`)
      .join('')

    const legendControl = L.control({ position: 'bottomright' })

    legendControl.onAdd = () => {
      const div = L.DomUtil.create('div', 'legend')

      div.innerHTML = `
          <div class="legend-caption">${legend.caption}</div>
          <div class="legend-gradient" style="background: ${gradientCss};"></div>
          <div class="legend-ticks">${tickLabels}</div>
        `

      return div
    }

    overlayLayer.addTo(map)
    legendControl.addTo(map)

    return () => {
      map.removeLayer(overlayLayer)
      legendControl.remove()
    }
  }

  useEffect(() => {
    if (!active || mode !== 'kde-heatmap' || !kdeData) return
    return renderKDEHeatmap(kdeData)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, active, mode, kdeData])

  // ---------- bandwidth sliders ----------
  function scheduleFetch(nextBandwidths) {
    clearTimeout(debounceTimerRef.current)

    debounceTimerRef.current = setTimeout(() => {
      fetchKDEHeatmap(nextBandwidths, currentClusterSet)
    }, 500)
  }

  function handleBandwidthInput(i, raw) {
    let value = Number(raw)
    const next = [...bandwidths]

    if (i > 0) value = Math.min(value, next[i - 1])
    if (i < next.length - 1) value = Math.max(value, next[i + 1])

    next[i] = value
    setBandwidths(next)
    scheduleFetch(next)
  }

  // Returns the slider rows as JSX (was DOM code)
  const [optimizing, setOptimizing] = useState(false)
  function buildSliders() {
    const levelNames = bandwidths.map((_, i) => {
      if (kdeData?.cluster_set !== 1) return `Level ${i}`
      const tier = runTiers[kdeData.cluster_levels?.[i]]
      return tier ? LEVEL_LABELS[tier] : `Level ${i}`
    })
    return (
      <>
        {bandwidths.map((bw, i) => (
          <Box
            sx={{ display: 'flex', flexDirection: 'column', width: '300px' }}
            key={i}
          >
            <Typography>
              {levelNames[i]} bandwidth: {Math.round(bw)}
            </Typography>

            <Slider
              aria-label='Small steps'
              valueLabelDisplay='auto'
              type='range'
              id={`bandwidth-slider-${i}`}
              className='bandwidth-slider'
              min={kdeData?.min_bandwidth}
              max={kdeData?.max_bandwidth}
              step={10}
              value={Math.round(bw)}
              onChange={(e) => handleBandwidthInput(i, e.target.value)}
            />
          </Box>
        ))}

        {bandwidths.length > 1 && (
          <Typography
            color='primary'
            sx={[
              { fontWeight: 600, fontSize: ' 16px' },
              (theme) =>
                theme.applyStyles('dark', {
                  color: '#E9C46A'
                })
            ]}
          >
            Constraint: {levelNames.join(' >= ')}{' '}
            {/* {bandwidths.map((_, i) => `Level ${i}`).join(' >= ')} */}
          </Typography>
        )}
        <Button
          color='success'
          variant='outlined'
          onClick={async () => {
            clearTimeout(debounceTimerRef.current)
            setOptimizing(true)
            try {
              await fetchKDEHeatmap(
                null,
                currentClusterSet,
                runIdRef.current,
                true
              )
            } finally {
              setOptimizing(false)
            }
          }}
        >
          {optimizing
            ? 'Optimizing… this can take a while'
            : 'Optimized Bandwidth'}
        </Button>
      </>
    )
  }
  //GIStar---------------------------------------------------------------
  async function fetchGIStar(value = distanceBand) {
    if (noTypes) {
      setGISData(null)
      return
    }
    const id = ++gistarRequestRef.current

    setIsLoading(true)
    try {
      const params = new URLSearchParams({ distance_band: value })
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)
      if (selectedNatures?.length) {
        params.append(
          'category',
          Array.isArray(selectedNatures)
            ? selectedNatures.join(',')
            : selectedNatures
        )
      }
      if (bbox) params.append('bbox', bbox)

      const res = await fetch(`${API}/gi-star-heatmap?${params}`)
      if (!res.ok) throw new Error('something wrong with gistar')
      const data = await res.json()

      if (id !== gistarRequestRef.current) return // stale response

      setGISData(data)
      setDistanceBand(data.distance_band)
    } catch (error) {
      console.log(error.message)
    } finally {
      if (id === gistarRequestRef.current) setIsLoading(false)
    }
  }
  function build_GI_Sliders() {
    return (
      <>
        <Box sx={{ display: 'flex', flexDirection: 'column', width: '300px' }}>
          <Typography>Distance Band: {Math.round(distanceBand)}</Typography>

          <Slider
            aria-label='Small steps'
            valueLabelDisplay='auto'
            type='range'
            id={`distance band`}
            className='bandwidth-slider'
            min={GISData?.min_distance_band}
            max={GISData?.max_distance_band}
            step={100}
            value={distanceBand}
            onChange={(_, value) => handleDistanceBand(value)}
          />
        </Box>
      </>
    )
  }
  function handleDistanceBand(value) {
    const newValue = value
    setDistanceBand(newValue)
    clearTimeout(distanceBandTimeBound.current)
    distanceBandTimeBound.current = setTimeout(() => {
      fetchGIStar(newValue)
    }, 400)
  }
  function renderGIStar(data) {
    const b = data.bounds
    const imageBounds = [
      [b.south, b.west],
      [b.north, b.east]
    ]

    const overlayLayer = L.imageOverlay(data.image, imageBounds, {
      opacity: 0.8
    })

    const legend = data.legend
    const gradientCss = `linear-gradient(to right, ${legend.colors.join(', ')})`

    const lastIdx = legend.ticks.length - 1
    const tickLabels = legend.ticks
      .map((t, i) => {
        const prefix = i === 0 ? ' <= ' : i === lastIdx ? '>= ' : ''
        //const max = i === lastIdx ? '>= ' : ''

        return `<span>${prefix}${Number(t.toPrecision(2))}</span>`
      })
      .join('')

    const legendControl = L.control({ position: 'bottomright' })

    legendControl.onAdd = () => {
      const div = L.DomUtil.create('div', 'legend')

      div.innerHTML = `
          <div class="legend-caption">${legend.caption}</div>
          <div class="legend-gradient" style="background: ${gradientCss};"></div>
          <div class="legend-ticks">${tickLabels}</div>
        `

      return div
    }

    overlayLayer.addTo(map)
    legendControl.addTo(map)

    return () => {
      map.removeLayer(overlayLayer)
      legendControl.remove()
    }
  }
  useEffect(() => {
    if (!active || mode !== 'gistar-heatmap') return
    fetchGIStar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, mode, startDate, endDate, bbox, natureKey])

  useEffect(() => {
    if (!active || mode !== 'gistar-heatmap' || !GISData) return
    return renderGIStar(GISData)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, active, mode, GISData])

  useEffect(() => () => clearTimeout(debounceTimerRef.current), [])

  // ---------- DBSCAN ----------
  async function fetchDbscan(
    visible = levelVisible,
    sliderValues = levelSliders
  ) {
    if (noTypes) {
      setLevelData(EMPTY_LEVELS)
      setDbscanError('Select at least one incident type')
      setStatus('error')
      return
    }
    const params = {}

    const enabledLevels = LEVEL_DRAW_ORDER.filter((level) => visible[level])

    if (!enabledLevels.length) {
      setDbscanError('Enable at least one cluster level')
      setStatus('error')
      return
    }
    setIsLoading(true)
    params.levels = enabledLevels.join(',')

    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    if (selectedNatures?.length) {
      params.category = Array.isArray(selectedNatures)
        ? selectedNatures.join(',')
        : selectedNatures
    }
    if (bbox) params.bbox = bbox
    enabledLevels.forEach((level) => {
      const { eps } = levelToParams(level, sliderValues[level])
      params[`${level}_eps`] = eps
    })

    const id = ++dbscanRequestRef.current

    setStatus('loading')
    setDbscanError('')
    const qs = new URLSearchParams(params).toString()

    try {
      const res = await fetch(`${API}/clusters${qs ? '?' + qs : ''}`)
      const body = await res.json()

      if (id !== dbscanRequestRef.current) return

      if (!res.ok) {
        throw new Error(body.error || `HTTP ${res.status}`)
      }
      const snapshot = body.frames && body.frames.length ? body.frames[0] : null
      const next = { ...EMPTY_LEVELS }
      if (snapshot) {
        enabledLevels.forEach((level) => {
          if (snapshot.levels[level]) next[level] = snapshot.levels[level]
        })
      }
      const hasClusters = Object.values(next).some(
        (level) => level?.metadata?.n_clusters > 0
      )
      setDbscanStatus(hasClusters ? 'available' : 'no_cluster_levels')

      // keep this run: /kde-heatmap needs it for the "Includes cluster analysis" option
      runIdRef.current = body.run_id ?? null
      setDbscanRunId(body.run_id ?? null)
      setRunTiers(enabledLevels)
      setLevelData(next) // stats + layers + legend all derive from this
      setStatus('ready')
      clustersLoadedRef.current = true

      // the backend now holds fresh cluster results for this run_id, so refresh the KDE
      // (this updates dbscan_status and enables "Includes cluster analysis").
      // Old bandwidths may no longer match the levels -> send null and let the backend pick defaults.
      // Cluster set 0 always has exactly one level, so its value is still valid.
      // const refreshBandwidths =
      //   currentClusterSet === 1 || !bandwidths.length ? null : bandwidths

      // fetchKDEHeatmap(refreshBandwidths, currentClusterSet, runIdRef.current)
      if (currentClusterSet === 1) {
        // B was built from the old run, so it is no longer valid (diagram: C only)
        kdeRequestRef.current++ // ignore any KDE response still in flight
        setKdeData(null)
        setCurrentClusterSet(0)
      }
      //  else {
      //   // A stays valid; refresh it so dbscan_status stays current
      //   fetchKDEHeatmap(
      //     !bandwidths.length ? null : bandwidths,
      //     currentClusterSet,
      //     runIdRef.current
      //   )
      // }
    } catch (err) {
      if (id !== dbscanRequestRef.current) return
      console.error('DBSCAN fetch failed:', err)
      setStatus('error')
      setDbscanError(err.message || 'Failed to load DBSCAN data')
    } finally {
      if (id === dbscanRequestRef.current) setIsLoading(false)
    }
  }

  // load clusters the first time we enter cluster mode (or after the date range changes)
  useEffect(() => {
    if (active && mode === 'clusters' && !clustersLoadedRef.current)
      fetchDbscan()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, mode, dataVersion])

  // syncClusterLayers: draw the visible level layers, cleanup removes them
  useEffect(() => {
    if (!active || mode !== 'clusters') return

    const groups = LEVEL_DRAW_ORDER.filter(
      (l) => levelData[l] && levelVisible[l]
    ).map((l) => renderLevelLayer(l, levelData[l]).addTo(map))

    return () => groups.forEach((g) => map.removeLayer(g))
  }, [map, active, mode, levelData, levelVisible])

  // cluster legend control
  // cluster legend control
  useEffect(() => {
    if (!active || mode !== 'clusters') return

    const sections = buildClusterLegend(levelData, levelVisible)
    if (!sections.replace(/<[^>]*>/g, '').trim()) return

    const clusterLegendControl = L.control({ position: 'bottomright' })

    clusterLegendControl.onAdd = () => {
      const div = L.DomUtil.create('div', 'cluster-legend')
      div.classList.toggle('collapsed', legendCollapsed)

      div.innerHTML =
        `<button type="button" class="legend-toggle" aria-expanded="${!legendCollapsed}">` +
        `<span>Legend</span><span class="legend-chevron">&#9660;</span></button>` +
        `<div class="legend-body">${sections}</div>`

      div.querySelector('.legend-toggle').addEventListener('click', (e) => {
        legendCollapsed = !legendCollapsed
        div.classList.toggle('collapsed', legendCollapsed)
        e.currentTarget.setAttribute('aria-expanded', String(!legendCollapsed))
      })

      L.DomEvent.disableScrollPropagation(div)
      L.DomEvent.disableClickPropagation(div)
      return div
    }

    clusterLegendControl.addTo(map)

    return () => clusterLegendControl.remove()
  }, [map, active, mode, levelData, levelVisible])

  useEffect(() => {
    map.invalidateSize()
  }, [map, active, mode])

  // ---------- events (were addEventListener) ----------
  function handleLevelToggle(level, checked) {
    const next = { ...levelVisible, [level]: checked }
    setLevelVisible(next)

    if (mode === 'clusters') {
      fetchDbscan(next, levelSliders)
    }
  }

  function handleDbscanReset() {
    setLevelVisible(ALL_VISIBLE)
    setLevelSliders(DEFAULT_LEVEL_SLIDERS)
    setDbscanError('')
    fetchDbscan(ALL_VISIBLE, DEFAULT_LEVEL_SLIDERS)
  }

  function handleAnalysisChange(event) {
    const value = event.target.value
    if (value === 'clusters') {
      setMode('clusters')
      return
    }

    if (value.startsWith('kde-')) {
      setMode('kde-heatmap')
      setCurrentClusterSet(Number(value.replace('kde-', '')))
      return
    }

    if (value === 'gistar-heatmap') {
      setMode('gistar-heatmap')
    }
  }

  const radioValue = mode === 'kde-heatmap' ? `kde-${currentClusterSet}` : mode

  const clusterNote =
    dbscanStatus && dbscanStatus !== 'available'
      ? CLUSTER_STATUS_NOTES[dbscanStatus] || ''
      : ''

  const totalPts = LEVEL_DRAW_ORDER.map(
    (l) => levelData[l]?.metadata?.n_total
  ).find((v) => v !== undefined && v !== null)

  return (
    <>
      <Box sx={{ display: 'flex' }}></Box>
      <Box
        className='analysis-bar'
        ref={topBarRef}
        onMouseEnter={() => map.dragging.disable()}
        onMouseLeave={() => {
          if (!drawArea) map.dragging.enable()
        }}
        sx={[
          {
            position: 'relative',
            flexShrink: '0',
            display: active ? 'flex' : 'none',
            alignItems: 'center',
            gap: '1.5rem',
            padding: '0.6rem 1.2rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.64)',
            background: 'rgba(15, 15, 30, 0.95)',
            zIndex: 1000,
            cursor: 'default'
          },
          (theme) =>
            theme.applyStyles('light', {
              backgroundColor: 'white',
              borderBottom: '1px solid rgba(66, 62, 62, 0.64)'
            })
        ]}
      >
        <FormControl sx={{}}>
          <FormLabel>Cluster and Heat Map Lab: </FormLabel>

          <RadioGroup
            row
            aria-labelledby='analysis-radio-label'
            name='analysis-set'
            value={radioValue}
            onChange={handleAnalysisChange}
          >
            {clusterSetLabels.map((label, i) => (
              <FormControlLabel
                key={i}
                value={`kde-${i}`}
                control={<Radio size='small' />}
                label={label}
                // "Includes cluster analysis" (set 1) is disabled until there is a usable cluster run
                disabled={
                  i === 1 && !!dbscanStatus && dbscanStatus !== 'available'
                }
              />
            ))}

            <FormControlLabel
              value='clusters'
              control={<Radio size='small' />}
              label='Cluster Analysis'
            />
            <FormControlLabel
              value='gistar-heatmap'
              control={<Radio size='small' />}
              label='Getis-Ord Gi* Heat Map'
            />
          </RadioGroup>
          {clusterNote && <div className='analysis-note'>{clusterNote}</div>}
        </FormControl>
      </Box>

      <Box
        className='analysis-bar'
        ref={secondBarRef}
        onMouseEnter={() => map.dragging.disable()}
        onMouseLeave={() => {
          if (!drawArea) map.dragging.enable()
        }}
        sx={[
          {
            background: 'rgba(24, 24, 44, 0.95)',
            padding: '0.6rem 1.2rem',
            flexWrap: 'wrap',
            zIndex: 1000,
            flexShrink: 0,
            alignItems: 'center',
            gap: '1.5rem',
            borderBottom: ' 1px solid rgba(255, 255, 255, 0.08)',
            display: active ? 'flex' : 'none',
            position: 'relative',
            cursor: 'default'
          },
          (theme) =>
            theme.applyStyles('light', {
              backgroundColor: 'white',
              borderBottom: '1px solid rgba(66, 62, 62, 0.64)'
            })
        ]}
        id='secondary-bar'
        data-mode={mode}
        style={{
          display: active ? undefined : 'none',
          position: 'relative',
          zIndex: 1000
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: '1rem',
            flexWrap: 'wrap',
            zIndex: 1000
          }}
        >
          {mode === 'clusters' && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'flex-end',
                gap: '1rem',
                flexWrap: 'wrap',
                zIndex: 1000
              }}
            >
              {LEVEL_UI_ORDER.map((level) => (
                <Card
                  sx={[
                    {
                      width: '300px',
                      display: 'flex',
                      flexDirection: 'column',
                      borderLeft: () =>
                        level === 'street'
                          ? '5px solid #d32f2f'
                          : level === 'neighborhood'
                            ? '5px solid #29b6f6'
                            : '5px solid #66bb6a',

                      padding: '8px',
                      gap: 0
                    },
                    (theme) =>
                      theme.applyStyles('dark', {
                        background: 'rgba(43, 40, 56, 0.95)'
                      })
                  ]}
                  elevation={5}
                  key={level}
                  className={`level-block${levelVisible[level] ? '' : ' level-off'}`}
                  id={`level-block-${level}`}
                  data-level={level}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      position: 'relative'
                    }}
                  >
                    <Switch
                      size='small'
                      color={
                        level === 'street'
                          ? 'error'
                          : level === 'neighborhood'
                            ? 'info'
                            : 'success'
                      }
                      checked={levelVisible[level]}
                      onChange={(e) =>
                        handleLevelToggle(level, e.target.checked)
                      }
                    />

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography
                        sx={{ fontWeight: 600, fontSize: '16px' }}
                        color={
                          level === 'street'
                            ? 'error'
                            : level === 'neighborhood'
                              ? 'info'
                              : 'success'
                        }
                      >
                        {LEVEL_LABELS[level]}
                      </Typography>
                      <Typography sx={{ fontSize: '12px' }} color='text'>
                        {LEVEL_HINTS[level]}
                      </Typography>
                    </Box>
                  </Box>

                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography
                      sx={{ fontSize: '12px', fontWeight: 500 }}
                      color='text'
                    >
                      {' '}
                      Sparse
                    </Typography>
                    <Slider
                      disabled={!levelVisible[level] || isLoading}
                      sx={{ width: '60%' }}
                      valueLabelDisplay='auto'
                      // valueLabelFormat={(v) =>
                      //   `${levelToParams(level, v).eps.toLocaleString()} ft`
                      // }
                      valueLabelFormat={(v) =>
                        `${levelToParams(level, v).eps.toLocaleString()} ft`
                      }
                      aria-label='Default'
                      id={`slider-${level}`}
                      data-level={level}
                      min={LEVEL_PRESETS[level].epsMin}
                      max={LEVEL_PRESETS[level].epsMax}
                      step={10}
                      value={
                        levelSliders[level] ?? DEFAULT_LEVEL_SLIDERS[level]
                      }
                      color={
                        level === 'street'
                          ? 'error'
                          : level === 'neighborhood'
                            ? 'info'
                            : 'success'
                      }
                      onChange={(_, value) => {
                        const nextSliders = { ...levelSliders, [level]: value }
                        setLevelSliders(nextSliders)
                        clearTimeout(applyRef.current)
                        applyRef.current = setTimeout(() => {
                          fetchDbscan(levelVisible, nextSliders)
                        }, 800)
                      }}
                    />

                    <Typography
                      sx={{ fontSize: '12px', fontWeight: 500 }}
                      color='text'
                    >
                      {' '}
                      Dense
                    </Typography>
                  </Box>
                  <Typography
                    sx={{
                      fontSize: '14px',
                      fontWeight: 500,
                      textAlign: 'center'
                    }}
                    color='text'
                  >
                    ε ={' '}
                    {levelToParams(
                      level,
                      levelSliders[level] ?? DEFAULT_LEVEL_SLIDERS[level]
                    ).eps.toLocaleString()}{' '}
                    ft
                  </Typography>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-around'
                    }}
                  >
                    <Box
                      sx={[
                        {
                          backgroundColor: (theme) => theme.palette.grey[800],
                          padding: '4px 8px',
                          borderRadius: '4px'
                        },
                        (theme) =>
                          theme.applyStyles('light', {
                            backgroundColor: 'white'
                          })
                      ]}
                    >
                      <Typography
                        color='primary'
                        sx={{ fontWeight: 600, fontSize: '12px' }}
                      >
                        Clusters:{' '}
                        {levelData[level]?.metadata?.n_clusters ?? '—'}
                      </Typography>
                    </Box>
                    <Box
                      sx={[
                        {
                          backgroundColor: (theme) => theme.palette.grey[800],
                          padding: '4px 8px',
                          borderRadius: '4px'
                        },
                        (theme) =>
                          theme.applyStyles('light', {
                            backgroundColor: 'white'
                          })
                      ]}
                    >
                      <Typography
                        color='primary'
                        sx={{ fontWeight: 600, fontSize: '12px' }}
                      >
                        Noise: {levelData[level]?.metadata?.n_noise ?? '—'}
                      </Typography>
                    </Box>
                  </Box>
                </Card>
              ))}
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Button
                  variant='contained'
                  onClick={handleDbscanReset}
                  color='warning'
                  sx={{ width: '100px' }}
                >
                  <Typography sx={{ fontWeight: 600, fontSize: '12px' }}>
                    {' '}
                    Reset
                  </Typography>
                </Button>

                {/* shown now: the server rejects ranges over 60 days and says so here */}
                {dbscanError && (
                  <Typography color='error' sx={{ maxWidth: '220px' }}>
                    {dbscanError}
                  </Typography>
                )}

                <Box>
                  <Typography
                    color='text'
                    sx={{ fontWeight: 600, fontSize: '12px' }}
                  >
                    {' '}
                    Total points: {totalPts ?? '—'}
                  </Typography>
                </Box>
              </Box>
            </Box>
          )}
        </Box>
        <div id='bandwidth-controls'>{buildSliders()}</div>

        <div id='gistar-controls'>{build_GI_Sliders()}</div>
      </Box>
      <Box
        onMouseEnter={() => map.dragging.disable()}
        onMouseLeave={() => {
          if (!drawArea) map.dragging.enable()
        }}
        ref={thirdBarRef}
        className='analysis-bar'
        sx={[
          {
            position: 'relative',
            flexShrink: '0',
            display: active ? 'flex' : 'none',
            alignItems: 'center',
            gap: '1.5rem',
            padding: '0.6rem 1.2rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.64)',
            background: 'rgba(15, 15, 30, 0.95)',
            zIndex: 1000,
            cursor: 'default',
            py: 0.5
          },
          (theme) =>
            theme.applyStyles('light', {
              backgroundColor: 'white',
              borderBottom: '1px solid rgba(66, 62, 62, 0.64)'
            })
        ]}
      >
        <Typography sx={{ fontSize: '16px', fontWeight: 600 }} color='primary'>
          Valid map in report:
        </Typography>
        <Typography sx={{ fontSize: '14px', fontWeight: 600 }}>
          KDE heat map:{' '}
          <Button
            size='small'
            variant='contained'
            color={reportMapState.kde ? 'success' : 'warning'}
          >
            {` ${reportMapState.kde === 'all' ? 'Valid (All points)' : reportMapState.kde === 'cluster' ? 'Valid (By Cluster)' : 'Invalid'}`}
          </Button>
        </Typography>
        <Typography sx={{ fontSize: '14px', fontWeight: 600 }}>
          Cluster Analysis:{' '}
          <Button
            size='small'
            variant='contained'
            color={reportMapState.clusters ? 'success' : 'warning'}
          >
            {` ${reportMapState.clusters ? 'Valid ' : 'Invalid'}`}
          </Button>
        </Typography>
        <Typography sx={{ fontSize: '14px', fontWeight: 600 }}>
          Getis-Ord Gi*:{' '}
          <Button
            size='small'
            variant='contained'
            color={reportMapState.giStar ? 'success' : 'warning'}
          >
            {`${reportMapState.giStar ? 'Valid ' : 'Invalid'}`}
          </Button>
        </Typography>
      </Box>
    </>
  )
}

export default Analysis
