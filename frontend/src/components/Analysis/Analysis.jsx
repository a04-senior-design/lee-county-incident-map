import { useEffect, useRef, useState } from 'react'
import './Analysis.css'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

import Radio from '@mui/material/Radio'
import RadioGroup from '@mui/material/RadioGroup'
import FormControlLabel from '@mui/material/FormControlLabel'
import FormControl from '@mui/material/FormControl'
import FormLabel from '@mui/material/FormLabel'
import Box from '@mui/material/Box'
const API = 'http://localhost:5001/api'

const LEVEL_DRAW_ORDER = ['district', 'neighborhood', 'street']
const LEVEL_UI_ORDER = ['street', 'neighborhood', 'district'] // order of the control blocks

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
  neighborhood: { epsMax: 10000, epsMin: 3000 },
  street: { epsMax: 2500, epsMin: 300 }
}

const CLUSTER_STATUS_NOTES = {
  missing: 'Run cluster analysis first.',
  all_noise:
    'Last cluster run found only noise. Try larger epsilon values in Cluster Analysis.'
}

const EMPTY_LEVELS = { district: null, neighborhood: null, street: null }
const ALL_VISIBLE = { district: true, neighborhood: true, street: true }
const DEFAULT_LEVEL_SLIDERS = { district: 50, neighborhood: 50, street: 50 }

// ---------- pure helpers (same names as before) ----------
function levelToParams(level, sliderVal) {
  const t = sliderVal / 100
  const p = LEVEL_PRESETS[level]

  const eps = Math.round(
    Math.exp(Math.log(p.epsMax) + (Math.log(p.epsMin) - Math.log(p.epsMax)) * t)
  )

  return { eps }
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

// Returns the legend HTML string (the effect puts it on the map)
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
        `<div style="margin-bottom:0.4rem">` +
        `<strong style="font-size:0.7rem;color:#aaa;text-transform:uppercase;letter-spacing:0.05em">` +
        `${LEVEL_LABELS[level]}</strong>${rows}</div>`
      )
    })
    .join('')
}

const Analysis = ({ filteredListWithLocation, active }) => {
  const map = useMap()

  //Mode --------------
  const [mode, setMode] = useState('kde-heatmap')
  const [currentClusterSet, setCurrentClusterSet] = useState(0)
  const [clusterSetLabels, setClusterSetLabels] = useState([])
  const [dataVersion, setDataVersion] = useState(0) // bumps after the POST finishes

  // KDE
  const [kdeData, setKdeData] = useState(null) // last KDE response
  const [dbscanStatus, setDbscanStatus] = useState(null)
  const [bandwidths, setBandwidths] = useState([]) // was `sliders` / `valueLabels`

  // DBSCAN / clusters
  const [levelVisible, setLevelVisible] = useState(ALL_VISIBLE)
  const [levelSliders, setLevelSliders] = useState(DEFAULT_LEVEL_SLIDERS)
  const [levelData, setLevelData] = useState(EMPTY_LEVELS)
  const [status, setStatusState] = useState(null) // 'loading' | 'ready' | 'error'
  const [dbscanError, setDbscanError] = useState('')

  const debounceTimerRef = useRef(null)
  const clustersLoadedRef = useRef(false)
  const kdeRequestRef = useRef(0)
  const dbscanRequestRef = useRef(0)
  const lastSentRef = useRef('')
  const lastKdeKeyRef = useRef('')
  //prevent when using the slider on the lab, the map can be dragged
  const topBarRef = useRef(null)
  const secondBarRef = useRef(null)
  useEffect(() => {
    ;[topBarRef.current, secondBarRef.current].forEach((el) => {
      if (!el) return
      L.DomEvent.disableClickPropagation(el)
      L.DomEvent.disableScrollPropagation(el)
    })
  }, [])
  function setStatus(state) {
    setStatusState(state)
  }

  // ---------- send data to the backend ----------
  async function sendToBackend() {
    if (!filteredListWithLocation) return false

    try {
      const response = await fetch(`${API}/analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filteredListWithLocation)
      })

      const text = await response.text()

      console.log('Backend status:', response.status)
      console.log('Backend response:', text)
    } catch (error) {
      console.error('Error sending data:', error)
    }
    return true
  }

  useEffect(() => {
    if (!active || !filteredListWithLocation) return

    const signature = filteredListWithLocation
      .map((inc) => inc.source_incident_id)
      .join(',')
    if (signature === lastSentRef.current) return // same incidents, nothing to send
    lastSentRef.current = signature

    setKdeData(null) // avoid showing the old heat map while the new one loads

    sendToBackend().then(() => {
      clustersLoadedRef.current = false
      setLevelData(EMPTY_LEVELS)
      setDataVersion((v) => v + 1)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredListWithLocation, active])

  // ---------- KDE ----------
  function fetchKDEHeatmap(bandwidthsParam, clusterSet) {
    const params = new URLSearchParams()

    if (clusterSet !== undefined && clusterSet !== null) {
      params.append('cluster_set', clusterSet)
    }

    if (bandwidthsParam) {
      bandwidthsParam.forEach((bw) => params.append('bandwidth', bw))
    }

    const query = params.toString()
    const url = query ? `${API}/kde-heatmap?${query}` : `${API}/kde-heatmap`

    const id = ++kdeRequestRef.current

    fetch(url)
      .then(async (res) => {
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
      })
      .catch((err) => {
        if (id !== kdeRequestRef.current) return
        console.error('KDEHeatmap fetch failed: ', err)

        if (err.data) setDbscanStatus(err.data.dbscan_status ?? null)
      })
  }

  useEffect(() => {
    if (!active || mode !== 'kde-heatmap') return
    if (dataVersion === 0) return // wait for the first POST to finish

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
      .map((t) => `<span>${Number(t.toPrecision(2))}</span>`)
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
    }, 400)
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
  function buildSliders() {
    return (
      <>
        {bandwidths.map((bw, i) => (
          <div className='param-row' key={i}>
            <label htmlFor={`bandwidth-slider-${i}`}>
              Level {i} bandwidth: <span>{Math.round(bw)}</span>
            </label>
            <input
              type='range'
              id={`bandwidth-slider-${i}`}
              className='bandwidth-slider'
              min={kdeData?.min_bandwidth}
              max={kdeData?.max_bandwidth}
              step={1}
              value={bw}
              onChange={(e) => handleBandwidthInput(i, e.target.value)}
            />
          </div>
        ))}

        {bandwidths.length > 1 && (
          <div className='bandwidth-hint'>
            Constraint: {bandwidths.map((_, i) => `Level ${i}`).join(' >= ')}
          </div>
        )}
      </>
    )
  }

  useEffect(() => () => clearTimeout(debounceTimerRef.current), [])

  // ---------- DBSCAN ----------
  async function fetchDbscan(
    visible = levelVisible,
    sliderValues = levelSliders
  ) {
    const params = {}

    const enabledLevels = LEVEL_DRAW_ORDER.filter((level) => visible[level])

    if (!enabledLevels.length) {
      setDbscanError('Enable at least one cluster level')
      setStatus('error')
      return
    }

    params.levels = enabledLevels.join(',')

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

      setLevelData(next) // stats + layers + legend all derive from this
      setStatus('ready')
      clustersLoadedRef.current = true

      // CHANGED: the backend now holds fresh cluster results, so refresh the KDE
      // (this updates dbscan_status and enables "Includes cluster analysis")
      fetchKDEHeatmap(bandwidths.length ? bandwidths : null, currentClusterSet)
    } catch (err) {
      if (id !== dbscanRequestRef.current) return
      console.error('DBSCAN fetch failed:', err)
      setStatus('error')
      setDbscanError(err.message || 'Failed to load DBSCAN data')
    }
  }

  // load clusters the first time we enter cluster mode (or after new data)
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
  useEffect(() => {
    if (!active || mode !== 'clusters') return

    const sections = buildClusterLegend(levelData, levelVisible)
    if (!sections.replace(/<[^>]*>/g, '').trim()) return

    const clusterLegendControl = L.control({ position: 'bottomright' })

    clusterLegendControl.onAdd = () => {
      const div = L.DomUtil.create('div', 'cluster-legend')
      div.innerHTML = sections
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

    if (checked && !levelData[level] && mode === 'clusters') {
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
      <Box
        ref={topBarRef}
        sx={{
          position: 'relative',
          flexShrink: '0',
          display: active ? 'flex' : 'none',
          alignItems: 'center',
          gap: '1.5rem',
          padding: '0.6rem 1.2rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          background: 'rgba(15, 15, 30, 0.95)',
          zIndex: 1000
        }}
      >
        <div id='branding'>
          <strong>Cluster and Heat Map Lab</strong>
          <span>Lee County Incidents — dev prototype</span>
        </div>

        <FormControl>
          <FormLabel id='analysis-radio-label'>Analysis</FormLabel>
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
                control={<Radio />}
                label={label}
                // CHANGED: "Includes cluster analysis" (set 1) is disabled until the backend has cluster results
                disabled={
                  i === 1 && !!dbscanStatus && dbscanStatus !== 'available'
                }
              />
            ))}

            <FormControlLabel
              value='clusters'
              control={<Radio />}
              label='Cluster Analysis'
            />
            <FormControlLabel
              value='gistar-heatmap'
              control={<Radio />}
              label='Getis-Ord Gi* Heat Map'
            />
          </RadioGroup>
          {clusterNote && <div className='analysis-note'>{clusterNote}</div>}
        </FormControl>
      </Box>
      <div
        ref={secondBarRef}
        id='secondary-bar'
        className='control-bar'
        data-mode={mode}
        style={{
          display: active ? undefined : 'none',
          position: 'relative',
          zIndex: 1000
        }}
      >
        <div id='dbscan-controls'>
          {LEVEL_UI_ORDER.map((level) => (
            <div
              key={level}
              className={`level-block${levelVisible[level] ? '' : ' level-off'}`}
              id={`level-block-${level}`}
              data-level={level}
            >
              <div className='level-header'>
                <label className='toggle-label'>
                  <input
                    type='checkbox'
                    className='level-toggle'
                    data-level={level}
                    checked={levelVisible[level]}
                    onChange={(e) => handleLevelToggle(level, e.target.checked)}
                  />
                  <span className='toggle-track'></span>
                </label>

                <span className='level-name'>{LEVEL_LABELS[level]}</span>
                <span className='level-hint'>{LEVEL_HINTS[level]}</span>
              </div>

              <div className='level-slider-row'>
                <span>Sparse</span>

                <input
                  type='range'
                  className='level-slider'
                  id={`slider-${level}`}
                  data-level={level}
                  min='0'
                  max='100'
                  step='1'
                  value={levelSliders[level]}
                  onChange={(e) =>
                    setLevelSliders((s) => ({
                      ...s,
                      [level]: Number(e.target.value)
                    }))
                  }
                />

                <span>Dense</span>
              </div>

              <div className='level-stats'>
                <span className='stat-pill'>
                  Clusters:{' '}
                  <span id={`stat-clusters-${level}`}>
                    {levelData[level]?.metadata?.n_clusters ?? '—'}
                  </span>
                </span>

                <span className='stat-pill'>
                  Noise:{' '}
                  <span id={`stat-noise-${level}`}>
                    {levelData[level]?.metadata?.n_noise ?? '—'}
                  </span>
                </span>
              </div>
            </div>
          ))}

          <button id='dbscan-apply' onClick={() => fetchDbscan()}>
            Apply
          </button>

          <button id='dbscan-reset' onClick={handleDbscanReset}>
            Reset
          </button>

          <span id='dbscan-controls-error'>{dbscanError}</span>

          <div id='status-dot' className={status || ''}></div>

          <div className='stat-pill'>
            Total pts: <span id='stat-total'>{totalPts ?? '—'}</span>
          </div>
        </div>

        <div id='bandwidth-controls'>{buildSliders()}</div>

        <div id='gistar-controls'></div>
      </div>
    </>
  )
}

export default Analysis
