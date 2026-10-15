import { useState, useEffect} from 'react'
import { AuthContext } from './AuthContext'
const url = import.meta.env.VITE_API_BASE_URL
function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const setSession = (currentUser, tokenAccess) => {
    setUser({
      id: currentUser.id,
      email: currentUser.email,
      name: currentUser.name
    })
    setToken(tokenAccess)
    //console.log('in auth user and token are: ', currentUser.id, tokenAccess)
  }
  const logout = async () => {
    try {
      const res = await fetch(`${url}/auth/logout`, {
        credentials: 'include',
        method: 'POST'
      })

      if (!res.ok) throw new Error(data.error)
      const data = await res.json()
    } catch (error) {
      console.log(error.message)
    } finally {
      setUser(null)
      setToken(null)

    }
  }
  useEffect(() => {
    async function refreshToken() {
      try {
        const res = await fetch(`${url}/auth/refresh`, {
          credentials: 'include',
          method: 'POST'
        })
        const data = await res.json()

        if (!res.ok) throw new Error(data.error || 'refresh token has problem')
        setSession(data.user, data.access_token)
      } catch (error) {
        console.log(error.message)
      } finally {
        setAuthReady(true)
      }
    }
    refreshToken()
  }, [])
  // Funtion -------------------------------------

  return (
    <AuthContext.Provider
      value={{ user, token, authReady, setSession, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export default AuthProvider
