import { AppShell, Box, Container } from "@mantine/core";

export function Shell({ children }) {
  return (
    <AppShell padding={0} bg="transparent">
      <AppShell.Main>
        <Box className="app-shell min-h-screen px-4 py-6 text-white sm:px-8 sm:py-8">
          <Container size="xl" className="relative z-[1]">
            {children}
          </Container>
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
