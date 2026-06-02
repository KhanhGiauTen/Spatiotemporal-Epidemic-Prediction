export default function AboutPage() {
  return (
    <main className="page">
      <header className="topbar">
        <h1>About the Project</h1>
        <p>How the epidemic monitoring demo connects analysis outputs to an interactive web application.</p>
      </header>
      <section className="content prose">
        <h2>Objective</h2>
        <p>
          The Spatiotemporal Epidemic Prediction Engine analyzes contact, temporal, and location signals to support
          outbreak risk monitoring for a university project demo.
        </p>
        <h2>Pipeline</h2>
        <p>
          Existing Tasks 1-12 prepare data, build warehouse-style outputs, run clustering, classify outbreak risk, and
          analyze contact networks. Task 13 reads those exported CSV files and exposes them through a FastAPI service.
        </p>
        <h2>Application</h2>
        <p>
          The frontend is a Next.js application. Leaflet renders the interactive map, while the dashboard, prediction,
          cluster, and network pages fetch JSON data from the FastAPI backend.
        </p>
        <h2>Limitations</h2>
        <p>
          Real polygon boundaries are not available yet. The red outbreak areas are deterministic generated visual zones
          from cluster outputs, not administrative or surveyed geographic boundaries.
        </p>
      </section>
    </main>
  );
}
