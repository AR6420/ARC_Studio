import { Routes, Route } from 'react-router-dom'

function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
            <h1 className="text-3xl font-bold">Nexus Sim</h1>
          </div>
        }
      />
    </Routes>
  )
}

export default App
