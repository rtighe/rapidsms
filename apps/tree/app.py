#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import rapidsms
from models import *

class App(rapidsms.app.App):
    def start(self):
        pass
    
    def configure(self, last_message="There are no more questions.", **kwargs):
        self.last_message = last_message
    
    def handle(self, msg):
        # first check if the caller is registered.  if not, register them.  this is very 
        # similar to the polls app
        try:
            person = Person.objects.all().get(phone=msg.connection.identity)
        except Person.DoesNotExist:
            person = Person(phone=msg.connection.identity, name="unknown")
            person.save()
            self.debug("Person %s saved" % person)

        
        # if this caller doesn't have a "question" attribute,
        # they're not currently answering a question tree, so
        # just search for triggers and return
        sessions = Session.objects.all().filter(state__isnull=False).filter(person=person)
        if not sessions:
            try:
                tree = Tree.objects.get(trigger=msg.text)
                # start a new session for this person and save it
                session = Session(person=person, tree=tree, state=tree.root_state)
                session.save()
                self.debug("session %s saved" % session)
                #self.connections[msg.connection.identity] = tree.root_state
            
            # no trigger found? no big deal. the
            # message is probably for another app
            except Tree.DoesNotExist:
                return False
        
        # the caller is part-way though a question
        # tree, so check their answer and respond
        else:
            session = sessions[0]
            try:
                state = session.state
                self.debug(state)
                transition = Transition.objects.get(
                    current_state=state,
                    answer=msg.text)
            
            # not a valid answer, so remind
            # the user of the valid options.
            except Transition.DoesNotExist:
                transitions = Transition.objects.filter(current_state=state)
                # there are no defined answers.  therefore there are no more questions to ask 
                if len(transitions) == 0:
                    msg.respond("You are done with this survey.  Thanks for participating!")
                    # remove the connection so the caller can start a new session
                    session.state  = None
                    session.save()
                    # self.connections.pop(msg.connection.identity)
                    return
                else:
                    flat_answers = ", ".join([trans.answer for trans in transitions])
                    msg.respond('"%s" is not a valid answer. Pick one of: %s' % (msg.text, flat_answers))
                    return True
            
            # if this answer has a response, send it back to the user
            # before doing anything else. this means that they might
            # receive two messages (this, and the next question), but
            # avoids having to concatenate them.
            # czue - removing this functionality
            #if answer.response:
            #    msg.respond(answer.response)
            
            # no matter what we want to create an entry for this response
            # have to know what sequence number to insert
            ids = Entry.objects.all().filter(session=session).order_by('sequence_id').values_list('sequence_id', flat=True)
            if ids:
                # not sure why pop() isn't allowed...
                sequence = ids[len(ids) -1] + 1
            else:
                sequence = 1
            entry = Entry(session=session,sequence_id=sequence,transition=transition,text=msg.text)
            entry.save()
            self.debug("entry %s saved" % entry)
                
            
            
            # advance to the next question, or remove
            # this caller's state if there are no more
            # this might be "None" but that's ok, it will be the equivalent of ending the session
            session.state = transition.next_state
            session.save()
            self.debug("session %s saved" % session)
                #self.connections[msg.connection.identity] =\
                #        transition.next_state
                
               
                # sent the LAST_MESSAGE to end the conversation,
                # unless the last question triggered a response
                #if not answer.response:
                #    msg.respond(self.last_message)
        
        # if there is a next question ready to ask
        # (and this includes THE FIRST), send it along
        sessions = Session.objects.all().filter(state__isnull=False).filter(person=person)
        if sessions:
            state = sessions[0].state
            if state.question:
                msg.respond(state.question.text)
                self.info(state.question.text)
        
        # if we haven't returned long before now, we're
        # long committed to dealing with this message
        return True
