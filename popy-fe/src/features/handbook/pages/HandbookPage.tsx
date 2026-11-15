import { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { PageHeader } from '@/components/common';
import { ROUTES } from '@/constants';
import { useLocale } from '@/hooks/useLocale';
import { isElectron } from '@/services/serverConfig';
import {
  getHandbookSections,
  HANDBOOK_UI,
  SINHALA_FONT,
  type HandbookOperation,
  type HandbookParameter,
  type HandbookSection,
  type HandbookUi,
} from '../content';

const sectionHref = (id: string) =>
  isElectron() ? `#${ROUTES.HANDBOOK}` : `#${id}`;

const scrollToSection = (id: string) => {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (!isElectron()) {
    const next = `${window.location.pathname}${window.location.search}#${id}`;
    window.history.replaceState(null, '', next);
  }
};

const ParameterTable = ({
  rows,
  ui,
}: {
  rows: HandbookParameter[];
  ui: HandbookUi;
}) => (
  <TableContainer>
    <Table size="small" aria-label={ui.parameters}>
      <TableHead>
        <TableRow>
          <TableCell>{ui.field}</TableCell>
          <TableCell>{ui.required}</TableCell>
          <TableCell>{ui.whatItDoes}</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.name}>
            <TableCell sx={{ fontWeight: 600, verticalAlign: 'top' }}>
              {row.name}
            </TableCell>
            <TableCell sx={{ verticalAlign: 'top' }}>
              <Chip
                size="small"
                label={row.required ? ui.required : ui.optional}
                color={row.required ? 'primary' : 'default'}
                variant={row.required ? 'filled' : 'outlined'}
              />
            </TableCell>
            <TableCell>{row.details}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
);

const StepList = ({ steps }: { steps: string[] }) => (
  <Box
    component="ol"
    sx={{ m: 0, pl: 2.5, display: 'flex', flexDirection: 'column', gap: 0.75 }}
  >
    {steps.map((step) => (
      <Typography key={step} component="li" variant="body2">
        {step}
      </Typography>
    ))}
  </Box>
);

const NoteList = ({ notes }: { notes: string[] }) => (
  <Box
    component="ul"
    sx={{
      m: 0,
      pl: 2.5,
      display: 'flex',
      flexDirection: 'column',
      gap: 0.75,
    }}
  >
    {notes.map((note) => (
      <Typography key={note} component="li" variant="body2">
        {note}
      </Typography>
    ))}
  </Box>
);

const OperationBlock = ({
  operation,
  ui,
}: {
  operation: HandbookOperation;
  ui: HandbookUi;
}) => (
  <Stack spacing={1.5} sx={{ mt: 3 }}>
    <Typography variant="subtitle1" fontWeight={700}>
      {operation.title}
    </Typography>
    <Typography variant="body2">
      <Box component="span" fontWeight={600}>
        {ui.who}:{' '}
      </Box>
      {operation.who}
    </Typography>
    <Typography variant="body2">
      <Box component="span" fontWeight={600}>
        {ui.where}:{' '}
      </Box>
      {operation.path}
    </Typography>
    <Typography variant="subtitle2">{ui.steps}</Typography>
    <StepList steps={operation.steps} />
    {operation.parameters && operation.parameters.length > 0 && (
      <>
        <Typography variant="subtitle2">{ui.parameters}</Typography>
        <ParameterTable rows={operation.parameters} ui={ui} />
      </>
    )}
    {operation.notes && operation.notes.length > 0 && (
      <>
        <Typography variant="subtitle2">{ui.goodToKnow}</Typography>
        <NoteList notes={operation.notes} />
      </>
    )}
  </Stack>
);

const SectionCard = ({
  section,
  ui,
}: {
  section: HandbookSection;
  ui: HandbookUi;
}) => (
  <Card id={section.id} component="section" sx={{ scrollMarginTop: 88 }}>
    <CardContent>
      <Typography variant="h6" gutterBottom>
        {section.title}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {section.summary}
      </Typography>
      {section.notes && section.notes.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <NoteList notes={section.notes} />
        </Box>
      )}
      {section.operations?.map((operation) => (
        <Box key={operation.title}>
          <Divider sx={{ mt: 3 }} />
          <OperationBlock operation={operation} ui={ui} />
        </Box>
      ))}
      {section.topics && section.topics.length > 0 && (
        <Stack spacing={2} sx={{ mt: 2 }}>
          {section.topics.map((topic) => (
            <Box key={topic.title}>
              <Typography variant="subtitle2">{topic.title}</Typography>
              <Typography variant="body2" color="text.secondary">
                {topic.body}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}
    </CardContent>
  </Card>
);

export const HandbookPage = () => {
  const { locale } = useLocale();
  const ui = HANDBOOK_UI[locale];
  const sections = getHandbookSections(locale);
  const [activeId, setActiveId] = useState(sections[0].id);

  useEffect(() => {
    const hash = window.location.hash.replace('#', '');
    if (
      hash &&
      !hash.startsWith('/') &&
      sections.some((section) => section.id === hash)
    ) {
      setActiveId(hash);
      document.getElementById(hash)?.scrollIntoView({ block: 'start' });
    }

    const nodes = sections.map((section) =>
      document.getElementById(section.id),
    ).filter((node): node is HTMLElement => node !== null);

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target.id) setActiveId(visible.target.id);
      },
      { rootMargin: '-80px 0px -55% 0px', threshold: [0.15, 0.4] },
    );

    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [sections]);

  return (
    <Box
      sx={
        locale === 'si'
          ? {
              '& .MuiTypography-root, & .MuiTableCell-root, & .MuiChip-label': {
                fontFamily: SINHALA_FONT,
              },
            }
          : undefined
      }
    >
      <PageHeader title={ui.title} subtitle={ui.subtitle} />
      <Box
        sx={{
          display: 'grid',
          gap: 3,
          alignItems: 'start',
          gridTemplateColumns: { xs: '1fr', md: '220px 1fr' },
        }}
      >
        <Box
          component="nav"
          aria-label={ui.sections}
          sx={{
            display: 'flex',
            flexDirection: { xs: 'row', md: 'column' },
            flexWrap: 'wrap',
            gap: 0.5,
            position: { md: 'sticky' },
            top: { md: 80 },
          }}
        >
          {sections.map((section) => {
            const selected = section.id === activeId;
            return (
              <Link
                key={section.id}
                href={sectionHref(section.id)}
                underline="none"
                color={selected ? 'primary.contrastText' : 'text.primary'}
                onClick={(event) => {
                  event.preventDefault();
                  setActiveId(section.id);
                  scrollToSection(section.id);
                }}
                sx={{
                  px: 1.5,
                  py: 0.75,
                  borderRadius: 2,
                  typography: 'body2',
                  fontWeight: selected ? 700 : 500,
                  bgcolor: selected ? 'primary.main' : 'transparent',
                  '&:hover': {
                    bgcolor: selected ? 'primary.dark' : 'action.hover',
                  },
                }}
              >
                {section.title}
              </Link>
            );
          })}
        </Box>
        <Stack spacing={3}>
          {sections.map((section) => (
            <SectionCard key={section.id} section={section} ui={ui} />
          ))}
        </Stack>
      </Box>
    </Box>
  );
};

export default HandbookPage;
