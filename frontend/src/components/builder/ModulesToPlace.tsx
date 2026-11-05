import { Link } from "react-router-dom";
import type { ModuleToPlace } from "@/lib/api";

interface ModulesToPlaceProps {
  modules: ModuleToPlace[];
  rackId: number | null;
}

/** Confirmed from a photo, not on the rig yet. Placing one goes through the rack route, which checks fit. */
export default function ModulesToPlace({ modules, rackId }: ModulesToPlaceProps) {
  if (modules.length === 0) return null;
  return (
    <div className="status status-warning builder-warnings" role="status">
      <p>
        <strong>Still to place.</strong> A photo gives no row or HP, and generation only uses
        modules placed on the rig.
      </p>
      <ul>
        {modules.map((module) => (
          <li key={module.instance_id}>
            {[module.manufacturer, module.model].filter(Boolean).join(" ") ||
              module.module_revision_id}
            {module.module_id == null ? (
              <>
                , no catalog match yet. Find it in the <Link to="/modules">module gallery</Link>.
              </>
            ) : rackId != null ? (
              <>
                {" "}
                <Link to={`/racks/${rackId}/edit?module_id=${module.module_id}`}>Place it</Link>
              </>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
