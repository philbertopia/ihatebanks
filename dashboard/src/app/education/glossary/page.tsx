import EducationLayout from "@/components/education/EducationLayout";
import GlossarySearch from "@/components/education/GlossarySearch";
import { getAllGlossaryEntries } from "@/lib/content";

export const metadata = {
  title: "Education Glossary | I Hate Banks",
  description: "Comprehensive options trading and strategy glossary.",
};

export default async function GlossaryPage() {
  const glossary = await getAllGlossaryEntries();

  return (
    <EducationLayout
      title="Glossary"
      description="A searchable reference of options trading terms, execution concepts, and strategy language."
    >
      <GlossarySearch entries={glossary} />
    </EducationLayout>
  );
}