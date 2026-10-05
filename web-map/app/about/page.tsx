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
          cluster, and network pages use same-origin Next.js endpoints backed by aggregate snapshots exported through
          the original FastAPI analysis code. The complete ETL and model pipeline runs locally, not on this host.
        </p>
        <h2>Limitations</h2>
        <p>
          Real polygon boundaries are not available yet. The red areas are deterministic generated visual zones
          from cluster outputs, not administrative or surveyed geographic boundaries.
        </p>
        <p>Only up to 50 clusters with at least 20 records are included in the public cluster excerpt. Individual-level data is excluded. The scoring sandbox uses a simple illustrative rule, not a trained model or clinical advice.</p>
      </section>
    </main>
  );
}
