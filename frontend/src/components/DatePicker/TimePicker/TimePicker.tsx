import { useState, useEffect, useRef, ChangeEvent } from 'react'
import { ActionIcon } from '@mantine/core'
import { TimeInput } from '@mantine/dates'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import { Popover, Button } from '@mantine/core'
interface Props {
  label: string
  draftRange: string
  setDraftRange: React.Dispatch<React.SetStateAction<string[]>>
  index: number
}

function TimePicker({ label, draftRange, setDraftRange, index }: Props) {
  const [opened, setOpened] = useState(false)
  const [time, setTime] = useState<string>('')
  const ref = useRef<HTMLInputElement>(null)
  //   useEffect(() => {
  //     console.log('time here', time)
  //   }, [time])
  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.value
    setDraftRange((prev) => {
      const updated = [...prev]
      updated[index] = newValue
      return updated
    })
  }
  //   useEffect(() => {
  //     console.log('time after change: ', timeRange)
  //   }, [timeRange])
  const pickerControl = (
    <ActionIcon
      variant='subtle'
      color='gray'
      onClick={() => ref.current?.showPicker()}
    >
      <AccessTimeIcon />
    </ActionIcon>
  )

  return (
    <TimeInput
      label={label}
      ref={ref}
      value={draftRange}
      rightSection={pickerControl}
      onChange={handleChange}
    />
  )
}

export default TimePicker
