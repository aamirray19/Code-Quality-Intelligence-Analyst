import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";

interface FindingsFilterBarProps {
  severity: string | undefined;
  agent: string | undefined;
  filePath: string | undefined;
  onSeverityChange: (value: string | undefined) => void;
  onAgentChange: (value: string | undefined) => void;
  onFilePathChange: (value: string | undefined) => void;
  availableSeverities: string[];
  availableAgents: string[];
}

const FindingsFilterBar = ({
  severity,
  agent,
  filePath,
  onSeverityChange,
  onAgentChange,
  onFilePathChange,
  availableSeverities,
  availableAgents,
}: FindingsFilterBarProps) => {
  return (
    <div className="flex flex-col sm:flex-row gap-4 mb-6">
      {/* Severity Filter */}
      <div className="flex-1">
        <label className="text-sm font-medium mb-2 block">Severity</label>
        <Select
          value={severity ?? "all"}
          onValueChange={(value) => onSeverityChange(value === "all" ? undefined : value)}
        >
          <SelectTrigger>
            <SelectValue placeholder="All severities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {availableSeverities.map((sev) => (
              <SelectItem key={sev} value={sev}>
                {sev}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Agent Filter */}
      <div className="flex-1">
        <label className="text-sm font-medium mb-2 block">Agent</label>
        <Select
          value={agent ?? "all"}
          onValueChange={(value) => onAgentChange(value === "all" ? undefined : value)}
        >
          <SelectTrigger>
            <SelectValue placeholder="All agents" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {availableAgents.map((ag) => (
              <SelectItem key={ag} value={ag}>
                {ag}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* File Path Filter */}
      <div className="flex-1">
        <label className="text-sm font-medium mb-2 block">File Path</label>
        <Input
          type="text"
          placeholder="Filter by file path..."
          value={filePath ?? ""}
          onChange={(e) => onFilePathChange(e.target.value || undefined)}
        />
      </div>
    </div>
  );
};

export default FindingsFilterBar;
