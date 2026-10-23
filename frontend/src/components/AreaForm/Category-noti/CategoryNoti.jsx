import Autocomplete from '@mui/material/Autocomplete'
import TextField from '@mui/material/TextField'
import { useEffect, useState } from 'react'

export default function LimitTags({
  url,
  setTypes,
  currentPicked,
  setCurrentPicked
}) {
  const [categories, setCategories] = useState([])
  const [fullList, setFullList] = useState(null)

  const [allTypesPicked, setAllTypesPicked] = useState(false)
  const emptiedList = []

  useEffect(() => {
    async function getCategoriesList() {
      try {
        const res = await fetch(`${url}/incident-types`)
        if (!res.ok) throw new Error('categories list has problem')
        const data = await res.json()
        console.log(data)
        const list = data?.types.map((item) => item.code)
        const listWithAllTypes = ['ALL TYPES', ...list]
        console.log('list here: ', listWithAllTypes)
        setCategories(listWithAllTypes)
        setFullList(list) //this list will be return when user pick alltype
      } catch (error) {
        console.log(error.message)
      }
    }
    getCategoriesList()
  }, [])
  useEffect(() => {
    if (currentPicked[0] === 'ALL TYPES') {
      setTypes(fullList)
      return
    }
    setTypes(currentPicked)
  }, [currentPicked])
  const handleOption = (newValue) => {
    setCurrentPicked(newValue)
    //console.log('alo ', newValue)
    for (const pick of newValue) {
      //of: interate through value, in: through index
      if (pick === 'ALL TYPES') {
        setCurrentPicked(['ALL TYPES'])
        setAllTypesPicked(true)
        return
      }
    }
    setAllTypesPicked(false)
    return
  }
  return (
    <Autocomplete
      multiple
      limitTags={2}
      id='multiple-limit-tags'
      options={allTypesPicked ? emptiedList : categories}
      value={currentPicked}
      onChange={(_, newValue) => handleOption(newValue)}
      defaultValue={categories[0] ?? []}
      renderInput={(params) => (
        <TextField
          {...params}
          label='Incident types'
          placeholder='Types'
          variant='filled'
        />
      )}
      sx={{ width: '350px' }}
    />
  )
}
