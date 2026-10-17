import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

const Sheet = DialogPrimitive.Root
const SheetTrigger = DialogPrimitive.Trigger
const SheetClose = DialogPrimitive.Close

// Radix portals to document.body by default. The HUD's color tokens and
// button defaults are scoped to .hud-root, so keep this portal inside that
// root when the HUD is mounted; otherwise the panel is transparent and its
// controls lose their theme styles.
const SheetContent = React.forwardRef(
  ({ className, children, side = 'responsive', ...props }, ref) => (
    <DialogPrimitive.Portal
      container={
        typeof document !== 'undefined'
          ? document.querySelector('.hud-root') || undefined
          : undefined
      }
    >
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm" />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          'fixed z-50 flex flex-col gap-4 overflow-y-auto border border-border bg-card p-5 text-card-foreground shadow-2xl transition-all duration-300',
          side === 'responsive' &&
            'inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl border-t border-x-0 border-b-0 sm:inset-y-0 sm:right-0 sm:left-auto sm:h-full sm:w-full sm:max-w-md sm:rounded-l-2xl sm:rounded-tr-none sm:border-l sm:border-t-0',
          side === 'bottom' &&
            'inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl border-t border-x-0 border-b-0',
          side === 'right' &&
            'inset-y-0 right-0 h-full w-full max-w-md rounded-l-2xl border-l',
          className
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          aria-label="Close panel"
          className="absolute right-4 top-4 rounded-lg p-1.5 opacity-70 transition-opacity hover:opacity-100 hover:bg-muted/40 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <X className="size-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
)
SheetContent.displayName = DialogPrimitive.Content.displayName

const SheetHeader = ({ className, ...props }) => (
  <div className={cn('flex flex-col gap-1 text-left', className)} {...props} />
)
const SheetTitle = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn('text-base font-semibold leading-tight', className)}
    {...props}
  />
))
SheetTitle.displayName = DialogPrimitive.Title.displayName
const SheetDescription = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-xs text-muted-foreground', className)}
    {...props}
  />
))
SheetDescription.displayName = DialogPrimitive.Description.displayName

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
}
