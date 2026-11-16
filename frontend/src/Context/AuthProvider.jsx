import { useState, useEffect, useRef } from 'react'
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
      const data = await res.json()
      if (!res.ok) throw new Error(data.error)
    } catch (error) {
      console.log(error.message)
    } finally {
      setUser(null)
      setToken(null)
    }
  }
  // If two callers refresh at once, they share one request.
  // Matters if the backend rotates refresh tokens (the second call would fail).
  const refreshPromiseRef = useRef(null)

  const refreshToken = () => {
    if (refreshPromiseRef.current) return refreshPromiseRef.current

    refreshPromiseRef.current = (async () => {
      try {
        const res = await fetch(`${url}/auth/refresh`, {
          credentials: 'include',
          method: 'POST'
        })
        const data = await res.json()

        if (!res.ok) throw new Error(data.error || 'refresh token has problem')
        setSession(data.user, data.access_token)
        return data.access_token // the caller needs the new token right now
      } catch (error) {
        console.log(error.message)
        // refresh failed: the session is really over, so stop showing "signed in"
        setUser(null)
        setToken(null)
        return null
      } finally {
        refreshPromiseRef.current = null
      }
    })()

    return refreshPromiseRef.current
  }

  useEffect(() => {
    refreshToken().finally(() => setAuthReady(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // Funtion -------------------------------------

  return (
    <AuthContext.Provider
      value={{ user, token, authReady, setSession, logout, refreshToken }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export default AuthProvider
