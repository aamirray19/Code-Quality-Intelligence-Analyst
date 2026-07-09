import Markdown from "react-markdown";

interface MarkdownReportViewProps {
  markdown: string;
}

const MarkdownReportView = ({ markdown }: MarkdownReportViewProps) => {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <Markdown>{markdown}</Markdown>
    </div>
  );
};

export default MarkdownReportView;
