"""Run clustering pipeline using Python 3.11 environment.
Loads data (CSV fallback), prepares features, runs KMeans and DBSCAN,
extracts weighted centroids and writes results to reports/.
"""
from pathlib import Path
import sys
import traceback

# Ensure repository root is on sys.path so we can import `src` as a package
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import pandas as pd
    import numpy as np
    from src import clustering
    from sklearn.decomposition import PCA
except Exception as e:
    print("Import error:", e)
    traceback.print_exc()
    sys.exit(2)

CSV = ROOT / 'data' / 'processed' / 'sashts_final_dataset.csv'
REPORT_DIR = ROOT / 'reports'
REPORT_DIR.mkdir(exist_ok=True)

try:
    # Try loading CSV fallback
    if CSV.exists():
        print('Loading CSV:', CSV)
        df = pd.read_csv(CSV)
    else:
        print('CSV fallback not found. Trying clustering.load_fact_exposure requires DB URL.')
        # Try to load via clustering.load_fact_exposure if DB URL set in src.config
        try:
            from src.config import DATABASE_URL
            df = clustering.load_fact_exposure(DATABASE_URL)
        except Exception as e:
            print('No CSV and DB load failed:', e)
            raise

    print('Rows loaded:', len(df))

    # Prepare features using helper
    df_pre, X, preproc, numeric_feats, cat_feats = clustering.prepare_clustering_features(df)
    print('Prepared features; X shape=', getattr(X, 'shape', None))

    # Run KMeans
    k = 4
    kmodel, klabels = clustering.run_kmeans(X, n_clusters=k)
    df_pre['kmeans_cluster'] = klabels

    # Run DBSCAN
    dmodel, dlabels = clustering.run_dbscan(X, eps=0.8, min_samples=5)
    df_pre['dbscan_cluster'] = dlabels

    # Extract centroids (use latitude/longitude if present)
    coord_cols = [c for c in ('latitude','longitude') if c in df_pre.columns]
    cent_k = clustering.extract_weighted_centroids(df_pre, klabels, coord_cols=coord_cols)
    cent_d = clustering.extract_weighted_centroids(df_pre, dlabels, coord_cols=coord_cols)

    # Export
    df_pre.to_csv(REPORT_DIR / 'ground_zero_clustered_cuboids.csv', index=False)
    cent_k.to_csv(REPORT_DIR / 'ground_zero_kmeans_centroids.csv', index=False)
    cent_d.to_csv(REPORT_DIR / 'ground_zero_dbscan_centroids.csv', index=False)

    print('Exported results to', REPORT_DIR)
    print('KMeans clusters:', len(set(klabels)))
    print('DBSCAN clusters (excluding -1):', len(set(dlabels) - {-1}))

except Exception as e:
    print('Error during run: ', e)
    traceback.print_exc()
    sys.exit(3)

print('Done')
